#!/bin/bash

# the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

INCEPTION_CHECKPOINT="${DIR}/pretrained_model/inception_v3/inception_v3.ckpt"
TFRECORD_DIR="${DIR}/data/TFRecord_data"
MODEL_DIR="${DIR}/model"
model=ShowAndTellAdvancedModel

model_dir_name=show_and_tell_advanced_model_only_semantic_attention

cd im2txt && CUDA_VISIBLE_DEVICES=0 python train.py \
  --input_file_pattern="${TFRECORD_DIR}/train-?????-of-?????.tfrecord" \
  --inception_checkpoint_file="${INCEPTION_CHECKPOINT}" \
  --train_dir="${MODEL_DIR}/${model_dir_name}" \
  --model=${model} \
  --initial_learning_rate=1.0 \
  --learning_rate_decay_factor=0.6 \
  --inception_return_tuple=True \
  --use_scheduled_sampling=False \
  --attention_mechanism=BahdanauAttention \
  --num_lstm_layers=1 \
  --predict_words_via_image_output=True \
  --use_semantic_attention=True \
  --use_separate_embedding_for_semantic_attention=True \
  --weight_semantic_memory_with_soft_prediction=True \
  --semantic_attention_word_hash_depth=128 \
  --support_ingraph=True \
  --number_of_steps=105000
