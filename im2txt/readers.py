# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provides readers configured for different datasets."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import utils
import tensorflow as tf
from tensorflow import logging
from tensorflow import flags
from tensorflow import gfile
from train_utils.image_processing import simple_process_image

FLAGS = flags.FLAGS
tf.flags.DEFINE_integer("num_refs", 5,
                        "Number of caption lines for each of the images.")


class BaseReader(object):
  """Inherit from this class when implementing new readers."""

  def prepare_reader(self, unused_filename_queue):
    """Create a thread for generating prediction and label tensors."""
    raise NotImplementedError()


class ImageCaptionReader(BaseReader):

  def __init__(self,
               num_refs=5,
               max_ref_length=30,
               is_training=True):
    self.num_refs = num_refs
    self.max_ref_length = max_ref_length 
    self.is_training = is_training

  def prepare_reader(self, filename_queue, batch_size=16):
    reader = tf.TFRecordReader()
    _, serialized_examples = reader.read(filename_queue)

    num_words = self.num_refs * self.max_ref_length
    feature_map = {
        "image/id": tf.FixedLenFeature([], tf.int64),
        "image/data": tf.FixedLenFeature([], tf.string),
        "image/ref_lengths": tf.FixedLenFeature([self.num_refs], tf.int64),
        "image/ref_words": tf.FixedLenFeature([num_words], tf.int64),
        "image/flipped_ref_lengths": tf.FixedLenFeature([self.num_refs], tf.int64),
        "image/flipped_ref_words": tf.FixedLenFeature([num_words], tf.int64),
      }
    if FLAGS.localization_attention:
      feature_map["image/localization"] = tf.FixedLenFeature([4*36], tf.float32)

    features = tf.parse_single_example(serialized_examples, features=feature_map)
    print(" features", features)

    # [1]
    image_id = features["image/id"] 
    print(" image_id", image_id)

    # [height, width, channels]
    encoded_image = features["image/data"]
    image = simple_process_image(encoded_image,
                                 flip=False,
                                 is_training=self.is_training)
    flipped_image = simple_process_image(encoded_image,
                                 flip=True,
                                 is_training=self.is_training)
    ref_words = features["image/ref_words"]
    ref_lengths = features["image/ref_lengths"]
    flipped_ref_words = features["image/flipped_ref_words"]
    flipped_ref_lengths = features["image/flipped_ref_lengths"]

    maybe_flipped_image, maybe_flipped_captions, maybe_flipped_ref_lengths = tf.cond(
                        tf.less(tf.random_uniform([],0,1.0), 0.5), 
                        lambda: [flipped_image, flipped_ref_words, flipped_ref_lengths], 
                        lambda: [image, ref_words, ref_lengths])
    print(" image", image)

    image_id = tf.reshape(image_id,
                          shape=[1])
    image = tf.reshape(maybe_flipped_image, 
                       shape=[1, FLAGS.image_height, FLAGS.image_width, FLAGS.image_channel])
    ref_words = tf.reshape(maybe_flipped_captions,
                           shape=[1, self.num_refs, self.max_ref_length])
    ref_lengths = tf.reshape(maybe_flipped_ref_lengths,
                             shape=[1, self.num_refs])

    if FLAGS.localization_attention:
      localizations = features["image/localization"]
      localizations = tf.reshape(localizations,
                               shape=[1, 36, 4])

    if FLAGS.multiple_references:
      input_seqs = ref_words
      target_seqs = tf.concat([input_seqs[:,:,1:], tf.zeros([1,self.num_refs,1], dtype=tf.int64)], axis=-1)
      input_mask = tf.reshape(tf.sequence_mask(tf.reshape(ref_lengths, [-1]), 
                                               maxlen=self.max_ref_length), 
                              [1, self.num_refs, self.max_ref_length])
      input_mask = tf.cast(input_mask, dtype=tf.int32)
      target_lengths = tf.maximum(ref_lengths - 1, 0)
      if FLAGS.localization_attention:
        return image, input_seqs, target_seqs, input_mask, target_lengths, localizations
      else:
        return image, input_seqs, target_seqs, input_mask, target_lengths
    else:
      images = tf.tile(image, multiples=[self.num_refs,1,1,1])
      input_seqs = tf.reshape(ref_words, 
                              shape=[self.num_refs, self.max_ref_length])
      target_seqs = tf.concat([input_seqs[:,1:], tf.zeros([self.num_refs,1], dtype=tf.int64)], 
                              axis=1)
      target_lengths = tf.reshape(tf.maximum(ref_lengths - 1, 0), shape=[self.num_refs])
      input_mask = tf.sequence_mask(target_lengths,
                                    maxlen=FLAGS.max_ref_length)
      input_mask = tf.cast(input_mask, dtype=tf.int32)
      if FLAGS.localization_attention:
        localizations = tf.tile(localizations, multiples=[self.num_refs,1,1])
        print(images, input_seqs, target_seqs, input_mask, target_lengths, localizations)
        return images, input_seqs, target_seqs, input_mask, target_lengths, localizations
      else:
        return images, input_seqs, target_seqs, input_mask, target_lengths


def get_input_data_tensors(reader,
                           data_pattern=None,
                           batch_size=16,
                           num_epochs=None,
                           is_training=True,
                           num_readers=1):
  reader = ImageCaptionReader(num_refs=FLAGS.num_refs,
                              max_ref_length=FLAGS.max_ref_length)
  logging.info("Using batch size of " + str(batch_size) + " for training.")
  with tf.name_scope("train_input"):
    files = gfile.Glob(data_pattern)
    print("number of training files:", len(files))
    if not files:
      raise IOError("Unable to find training files. data_pattern='" +
                    data_pattern + "'.")
    logging.info("Number of training files: %s.", str(len(files)))
    filename_queue = tf.train.string_input_producer(
        files, num_epochs=num_epochs, shuffle=True)

    training_data = [
        reader.prepare_reader(filename_queue) for _ in range(num_readers)
    ]

    return tf.train.shuffle_batch_join(
        training_data,
        batch_size=batch_size,
        capacity=batch_size * 8,
        min_after_dequeue=batch_size,
        allow_smaller_final_batch=False,
        enqueue_many=True)

class ImageCaptionTestReader(BaseReader):

  def __init__(self):
    self.is_training = False

  def prepare_reader(self, filename_queue, batch_size=16):
    reader = tf.TFRecordReader()
    _, serialized_examples = reader.read(filename_queue)

    feature_map = {
        "image/id": tf.FixedLenFeature([], tf.int64),
        "image/filename": tf.FixedLenFeature([], tf.string),
        "image/data": tf.FixedLenFeature([], tf.string),
      }
    if FLAGS.localization_attention:
      feature_map["image/localization"] = tf.FixedLenFeature([4*36], tf.float32)

    features = tf.parse_single_example(serialized_examples, features=feature_map)
    print(" features", features)

    # [1]
    image_id = features["image/id"] 
    print(" image_id", image_id)

    filename = features["image/filename"] 
    print(" filename", filename)

    # [height, width, channels]
    encoded_image = features["image/data"]
    image = simple_process_image(encoded_image,
                                 flip=False,
                                 is_training=self.is_training)
    print(" image", image)

    image_id = tf.reshape(image_id,
                          shape=[1])
    image = tf.reshape(image, 
                       shape=[1, FLAGS.image_height, FLAGS.image_width, FLAGS.image_channel])
    filename = tf.reshape(filename,
                          shape=[1])

    if FLAGS.localization_attention:
      localizations = features["image/localization"]
      localizations = tf.reshape(localizations,
                               shape=[1, 36, 4])
      return image, filename, localizations
    else:
      return image, filename

def get_test_input_data_tensors(reader,
                           data_pattern=None,
                           batch_size=16,
                           num_epochs=1,
                           num_readers=1):
  reader = ImageCaptionTestReader()
  logging.info("Using batch size of " + str(batch_size) + " for training.")
  with tf.name_scope("train_input"):
    files = gfile.Glob(data_pattern)
    print("number of training files:", len(files))
    if not files:
      raise IOError("Unable to find training files. data_pattern='" +
                    data_pattern + "'.")
    logging.info("Number of training files: %s.", str(len(files)))
    filename_queue = tf.train.string_input_producer(
        files, num_epochs=num_epochs, shuffle=True)

    training_data = reader.prepare_reader(filename_queue)

    return tf.train.batch(
        training_data,
        batch_size=batch_size,
        capacity=batch_size * 8,
        allow_smaller_final_batch=False,
        enqueue_many=True)
