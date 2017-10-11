# coding: utf-8
# Copyright 2017 challenger.ai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Build tfrecord data."""
# __author__ = 'Miao'
# python2.7
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import Counter
from collections import namedtuple
from datetime import datetime
import json
import os.path
import random
import sys

reload(sys)
sys.setdefaultencoding('utf8')
import threading
import jieba
import numpy as np
import tensorflow as tf

# input data
tf.flags.DEFINE_string("train_image_dir", "data/ai_challenger_caption_train_20170902/caption_train_images_20170902",
                       "Training image directory.")
tf.flags.DEFINE_string("validate_image_dir", "data/ai_challenger_caption_validation_20170910/caption_validation_images_20170910",
                       "Validation image directory.")

tf.flags.DEFINE_string("train_captions_file", "data/ai_challenger_caption_train_20170902/caption_train_annotations_20170902.json",
                       "Training captions JSON file.")
tf.flags.DEFINE_string("validate_captions_file", "data/ai_challenger_caption_validation_20170910/caption_validation_annotations_20170910.json",
                       "Validation captions JSON file.")

# use existing word counts file
tf.flags.DEFINE_string("word_counts_input_file",
                       "",
                       "If defined, use existing word_counts_file.")

# output files
tf.flags.DEFINE_string("output_dir", "data/TFRecord_data", "Output directory for tfrecords.")
tf.flags.DEFINE_string("word_counts_output_file",
                       "data/word_counts.txt",
                       "Output vocabulary file of word counts.")

# words parameters
tf.flags.DEFINE_string("start_word", "<S>",
                       "Special word added to the beginning of each sentence.")
tf.flags.DEFINE_string("end_word", "</S>",
                       "Special word added to the end of each sentence.")
tf.flags.DEFINE_string("unknown_word", "<UNK>",
                       "Special word meaning 'unknown'.")

# the minimum word count
tf.flags.DEFINE_integer("min_word_count", 4,
                        "The minimum number of occurrences of each word in the "
                        "training set for inclusion in the vocabulary.")

# threads
tf.flags.DEFINE_integer("num_threads", 8,
                        "Number of threads to preprocess the images.")

# sharding parameters
tf.flags.DEFINE_integer("train_shards", 280,
                        "Number of shards in training TFRecord files.")
tf.flags.DEFINE_integer("validate_shards", 4,
                        "Number of shards in validation TFRecord files.")
tf.flags.DEFINE_integer("test_shards", 8,
                        "Number of shards in testing TFRecord files.")

FLAGS = tf.flags.FLAGS



ImageMetadata = namedtuple("ImageMetadata",
                           ["id", "filename", "captions", "flip_captions"])


class Vocabulary(object):
    """Simple vocabulary wrapper."""

    def __init__(self, vocab, unk_id):
        """Initializes the vocabulary.
        Args:
          vocab: A dictionary of word to word_id.
          unk_id: Id of the special 'unknown' word.
        """
        self._vocab = vocab
        self._unk_id = unk_id

    def word_to_id(self, word):
        """Returns the integer id of a word string."""
        if word in self._vocab:
            return self._vocab[word]
        else:
            return self._unk_id

def load_vocab(vocab_file):
    if not tf.gfile.Exists(vocab_file):
      print("Vocab file %s not found.", vocab_file)
      exit()
    print("Initializing vocabulary from file: %s", vocab_file)

    with tf.gfile.GFile(vocab_file, mode="r") as f:
      reverse_vocab = list(f.readlines())
    reverse_vocab = [line.split()[0] for line in reverse_vocab]
    assert FLAGS.start_word in reverse_vocab
    assert FLAGS.end_word in reverse_vocab
    assert FLAGS.unk_word not in reverse_vocab

    unk_id = len(reverse_vocab)
    vocab_dict = dict([(x, y) for (y, x) in enumerate(reverse_vocab)])
    vocab = Vocabulary(vocab_dict, unk_id)
    return vocab



class ImageDecoder(object):
    """Helper class for decoding images in TensorFlow."""

    def __init__(self):
        # Create a single TensorFlow Session for all image decoding calls.
        self._sess = tf.Session()

        # TensorFlow ops for JPEG decoding.
        self._encoded_jpeg = tf.placeholder(dtype=tf.string)
        self._decode_jpeg = tf.image.decode_jpeg(self._encoded_jpeg, channels=3)

    def decode_jpeg(self, encoded_jpeg):
        image = self._sess.run(self._decode_jpeg,
                               feed_dict={self._encoded_jpeg: encoded_jpeg})
        assert len(image.shape) == 3
        assert image.shape[2] == 3
        return image


def _int64_feature(value):
    """Wrapper for inserting an int64 Feature into a SequenceExample proto."""
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))


def _bytes_feature(value):
    """Wrapper for inserting a bytes Feature into a SequenceExample proto."""
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[str(value)]))


def _int64_feature_list(values):
    """Wrapper for inserting an int64 FeatureList into a SequenceExample proto."""
    return tf.train.FeatureList(feature=[_int64_feature(v) for v in values])


def _bytes_feature_list(values):
    """Wrapper for inserting a bytes FeatureList into a SequenceExample proto."""
    return tf.train.FeatureList(feature=[_bytes_feature(v) for v in values])


def _to_sequence_example(image, decoder, vocab):
    """Builds a SequenceExample proto for an image-caption pair.
    Args:
      image: An ImageMetadata object.
      decoder: An ImageDecoder object.
      vocab: A Vocabulary object.
    Returns:
      A SequenceExample proto.
    """
    with tf.gfile.FastGFile(image.filename, "r") as f:
        encoded_image = f.read()

    try:
        decoder.decode_jpeg(encoded_image)
    except (tf.errors.InvalidArgumentError, AssertionError):
        print("Skipping file with invalid JPEG data: %s" % image.filename)
        return
    context = tf.train.Features(feature={
        "image/id": _int64_feature(image.id),
        "image/data": _bytes_feature(encoded_image),
    })

    assert len(image.captions) == 1
    caption = image.captions[0]
    caption_ids = [vocab.word_to_id(word) for word in caption]
    flip_caption = image.flip_captions[0]
    if not flip_caption:
        feature_lists = tf.train.FeatureLists(feature_list={
            "image/caption": _bytes_feature_list(caption),
            "image/caption_ids": _int64_feature_list(caption_ids)
        })
    else:
        flip_caption_ids = [vocab.word_to_id(word) for word in flip_caption]
        feature_lists = tf.train.FeatureLists(feature_list={
            "image/caption": _bytes_feature_list(caption),
            "image/caption_ids": _int64_feature_list(caption_ids),
            "image/flip_caption": _bytes_feature_list(flip_caption),
            "image/flip_caption_ids": _int64_feature_list(flip_caption_ids)
        })
    
    sequence_example = tf.train.SequenceExample(
        context=context, feature_lists=feature_lists)

    return sequence_example


def _process_image_files(thread_index, ranges, name, images, decoder, vocab,
                         num_shards):
    """Processes and saves a subset of images as TFRecord files in one thread.
    Args:
      thread_index: Integer thread identifier within [0, len(ranges)].
      ranges: A list of pairs of integers specifying the ranges of the dataset to
        process in parallel.
      name: Unique identifier specifying the dataset.
      images: List of ImageMetadata.
      decoder: An ImageDecoder object.
      vocab: A Vocabulary object.
      num_shards: Integer number of shards for the output files.
    """
    # Each thread produces N shards where N = num_shards / num_threads. For
    # instance, if num_shards = 128, and num_threads = 2, then the first thread
    # would produce shards [0, 64).
    num_threads = len(ranges)
    assert not num_shards % num_threads
    num_shards_per_batch = int(num_shards / num_threads)

    shard_ranges = np.linspace(ranges[thread_index][0], ranges[thread_index][1],
                               num_shards_per_batch + 1).astype(int)
    num_images_in_thread = ranges[thread_index][1] - ranges[thread_index][0]

    counter = 0
    for s in range(num_shards_per_batch):
        # Generate a sharded version of the file name, e.g. 'train-00002-of-00010'
        shard = thread_index * num_shards_per_batch + s
        output_filename = "%s-%.5d-of-%.5d.tfrecord" % (name, shard, num_shards)
        output_file = os.path.join(FLAGS.output_dir, output_filename)
        writer = tf.python_io.TFRecordWriter(output_file)

        shard_counter = 0
        images_in_shard = np.arange(shard_ranges[s], shard_ranges[s + 1], dtype=int)
        for i in images_in_shard:
            image = images[i]

            sequence_example = _to_sequence_example(image, decoder, vocab)
            if sequence_example is not None:
                writer.write(sequence_example.SerializeToString())
                shard_counter += 1
                counter += 1

            if not counter % 1000:
                print("%s [thread %d]: Processed %d of %d items in thread batch." %
                      (datetime.now(), thread_index, counter, num_images_in_thread))
                sys.stdout.flush()

        writer.close()
        print("%s [thread %d]: Wrote %d image-caption pairs to %s" %
              (datetime.now(), thread_index, shard_counter, output_file))
        sys.stdout.flush()
        shard_counter = 0
    print("%s [thread %d]: Wrote %d image-caption pairs to %d shards." %
          (datetime.now(), thread_index, counter, num_shards_per_batch))
    sys.stdout.flush()


def _process_dataset(name, images, vocab, num_shards):
    """Processes a complete data set and saves it as a TFRecord.
    Args:
      name: Unique identifier specifying the dataset.
      images: List of ImageMetadata.
      vocab: A Vocabulary object.
      num_shards: Integer number of shards for the output files.
    """
    # Break up each image into a separate entity for each caption.
    images = [ImageMetadata(image.id, image.filename, [caption], [flip_caption])
              for image in images for (caption,flip_caption) in zip(image.captions, image.flip_captions)]

    # Shuffle the ordering of images. Make the randomization repeatable.
    random.seed(12345)
    random.shuffle(images)

    # Break the images into num_threads batches. Batch i is defined as
    # images[ranges[i][0]:ranges[i][1]].
    num_threads = min(num_shards, FLAGS.num_threads)
    spacing = np.linspace(0, len(images), num_threads + 1).astype(np.int)
    ranges = []
    threads = []
    for i in range(len(spacing) - 1):
        ranges.append([spacing[i], spacing[i + 1]])

    # Create a mechanism for monitoring when all threads are finished.
    coord = tf.train.Coordinator()

    # Create a utility for decoding JPEG images to run sanity checks.
    decoder = ImageDecoder()

    # Launch a thread for each batch.
    print("Launching %d threads for spacings: %s" % (num_threads, ranges))
    for thread_index in range(len(ranges)):
        args = (thread_index, ranges, name, images, decoder, vocab, num_shards)
        t = threading.Thread(target=_process_image_files, args=args)
        t.start()
        threads.append(t)

    # Wait for all the threads to terminate.
    coord.join(threads)
    print("%s: Finished processing all %d image-caption pairs in data set '%s'." %
          (datetime.now(), len(images), name))


def _create_vocab(captions):
    """Creates the vocabulary of word to word_id.
    The vocabulary is saved to disk in a text file of word counts. The id of each
    word in the file is its corresponding 0-based line number.
    Args:
      captions: A list of lists of strings.
    Returns:
      A Vocabulary object.
    """
    print("Creating vocabulary.")
    counter = Counter()
    for c in captions:
        counter.update(c)
    print("Total words:", len(counter))

    # Filter uncommon words and sort by descending count.
    word_counts = [x for x in counter.items() if x[1] >= FLAGS.min_word_count]
    word_counts.sort(key=lambda x: x[1], reverse=True)
    print("Words in vocabulary:", len(word_counts))

    # Write out the word counts file.
    with tf.gfile.FastGFile(FLAGS.word_counts_output_file, "w") as f:
        f.write("\n".join(["%s %d" % (w, c) for w, c in word_counts]))
    print("Wrote vocabulary file:", FLAGS.word_counts_output_file)

    # Create the vocabulary dictionary.
    reverse_vocab = [x[0] for x in word_counts]
    unk_id = len(reverse_vocab)
    vocab_dict = dict([(x, y) for (y, x) in enumerate(reverse_vocab)])
    vocab = Vocabulary(vocab_dict, unk_id)

    return vocab


def _process_caption_jieba(caption):
    """Processes a Chinese caption string into a list of tonenized words.
    Args:
      caption: A string caption.
    Returns:
      A list of strings; the tokenized caption.
    """
    tokenized_caption = [FLAGS.start_word]
    tokenized_caption.extend(jieba.cut(caption, cut_all=False))
    tokenized_caption.append(FLAGS.end_word)
    return tokenized_caption


def _load_and_process_metadata(captions_file, image_dir):
    """Loads image metadata from a JSON file and processes the captions.
    Args:
      captions_file: Json file containing caption annotations.
      image_dir: Directory containing the image files.
    Returns:
      A list of ImageMetadata.
    """
    image_id = set([])
    id_to_captions = {}
    id_to_flip_captions = {}
    with open(captions_file, 'r') as f:
        caption_data = json.load(f)
    for data in caption_data:
        image_name = data['image_id'].split('.')[0]
        descriptions = data['caption']
        if 'flip_caption' not in data:
            flip_descriptions = [None] * len(descriptions)
        else:
            flip_descriptions = data['flip_caption']

        if image_name not in image_id:
            id_to_captions.setdefault(image_name, [])
            id_to_flip_captions.setdefault(image_name, [])
            image_id.add(image_name)

        caption_num = len(descriptions)
        assert caption_num == len(flip_descriptions)

        for i in range(caption_num):
            caption_temp = descriptions[i].strip().strip("。").replace('\n', '')
            flip_caption_temp = flip_descriptions[i].strip().strip("。").replace('\n', '') \
                                if flip_descriptions[i] else None
            if caption_temp != '':
                id_to_captions[image_name].append(caption_temp)
                id_to_flip_captions[image_name].append(flip_caption_temp)


    print("Loaded caption metadata for %d images from %s and image_id num is %s" %
          (len(id_to_captions), captions_file, len(image_id)))
    # Process the captions and combine the data into a list of ImageMetadata.
    print("Proccessing captions.")
    image_metadata = []
    num_captions = 0
    id = 0
    for base_filename in image_id:
        filename = os.path.join(image_dir, base_filename + '.jpg')
        # captions = [_process_caption(c) for c in id_to_captions[base_filename]]
        captions = [_process_caption_jieba(c) for c in id_to_captions[base_filename]]
        flip_captions = []
        for c in id_to_flip_captions[base_filename]:
            if c:
                flip_captions.append(_process_caption_jieba)
            else:
                flip_captions.append(None)

        image_metadata.append(ImageMetadata(id, filename, captions, flip_captions))
        id = id + 1
        num_captions += len(captions)
    print("Finished processing %d captions for %d images in %s" %
          (num_captions, len(id_to_captions), captions_file))
    return image_metadata


def main(unused_argv):
    def _is_valid_num_shards(num_shards):
        """Returns True if num_shards is compatible with FLAGS.num_threads."""
        return num_shards < FLAGS.num_threads or not num_shards % FLAGS.num_threads

    assert _is_valid_num_shards(FLAGS.train_shards), (
        "Please make the FLAGS.num_threads commensurate with FLAGS.train_shards")
    assert _is_valid_num_shards(FLAGS.validate_shards), (
        "Please make the FLAGS.num_threads commensurate with FLAGS.validate_shards")
    assert _is_valid_num_shards(FLAGS.test_shards), (
        "Please make the FLAGS.num_threads commensurate with FLAGS.test_shards")

    if not tf.gfile.IsDirectory(FLAGS.output_dir):
        tf.gfile.MakeDirs(FLAGS.output_dir)

    # Load image metadata from caption files.
    train_dataset = _load_and_process_metadata(FLAGS.train_captions_file,
                                                    FLAGS.train_image_dir)
    validate_dataset = _load_and_process_metadata(FLAGS.validate_captions_file,
                                                  FLAGS.validate_image_dir)

    """
    # Redistribute the MSCOCO data as follows:
    #   train_dataset = 100% of mscoco_train_dataset + 85% of mscoco_validate_dataset.
    #   validate_dataset = 5% of mscoco_validate_dataset (for validation during training).
    #   test_dataset = 10% of mscoco_validate_dataset (for final evaluation).
    train_cutoff = int(0.85 * len(mscoco_validate_dataset))
    validate_cutoff = int(0.90 * len(mscoco_validate_dataset))
    train_dataset = mscoco_train_dataset + mscoco_validate_dataset[0:train_cutoff]
    validate_dataset = mscoco_validate_dataset[train_cutoff:validate_cutoff]
    test_dataset = mscoco_validate_dataset[validate_cutoff:]
    """


    # Create vocabulary from the training captions.
    train_captions = [c for image in train_dataset for c in image.captions]
    if FLAGS.word_counts_input_file:
        vocab = load_vocab(FLAGS.word_counts_input_file)
    else:
        vocab = _create_vocab(train_captions)

    _process_dataset("train", train_dataset, vocab, FLAGS.train_shards)
    #_process_dataset("val", validate_dataset, vocab, FLAGS.validate_shards)
    # _process_dataset("test", test_dataset, vocab, FLAGS.test_shards)

if __name__ == "__main__":
    tf.app.run()
