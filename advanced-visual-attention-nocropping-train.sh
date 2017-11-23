#!/bin/bash

# the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

INCEPTION_CHECKPOINT="${DIR}/pretrained_model/inception_v3/inception_v3.ckpt"
TFRECORD_DIR="${DIR}/data/Loc_TFRecord_data"
MODEL_DIR="${DIR}/model"

model=ShowAndTellAdvancedModel
model_dir_name=show_and_tell_advanced_model_visual_attention_nocropping

cd im2txt 


#CUDA_VISIBLE_DEVICES=0 python train.py \
#  --input_file_pattern="${TFRECORD_DIR}/train-?????-of-?????.tfrecord" \
#  --inception_checkpoint_file="${INCEPTION_CHECKPOINT}" \
#  --train_dir="${MODEL_DIR}/${model_dir_name}" \
#  --model=${model} \
#  --initial_learning_rate=1.0 \
#  --learning_rate_decay_factor=0.66 \
#  --cropping_images=False \
#  --inception_return_tuple=True \
#  --use_scheduled_sampling=False \
#  --use_attention_wrapper=True \
#  --attention_mechanism=BahdanauAttention \
#  --num_lstm_layers=1 \
#  --support_ingraph=True \
#  --number_of_steps=30000

CUDA_VISIBLE_DEVICES=0 python train.py \
  --input_file_pattern="${TFRECORD_DIR}/train-?????-of-?????.tfrecord" \
  --inception_checkpoint_file="${INCEPTION_CHECKPOINT}" \
  --train_dir="${MODEL_DIR}/${model_dir_name}" \
  --model=${model} \
  --initial_learning_rate=1.0 \
  --learning_rate_decay_factor=0.66 \
  --inception_return_tuple=True \
  --use_scheduled_sampling=False \
  --use_attention_wrapper=True \
  --attention_mechanism=BahdanauAttention \
  --num_lstm_layers=1 \
  --support_ingraph=True \
  --train_inception_with_decay=True \
  --rl_training=True \
  --rl_training_loss="SelfCriticalLoss" \
  --reader=ImageCaptionReader \
  --multiple_references=True \
  --cropping_images=False \
  --document_frequency_file="${DIR}/data/document_frequency.json" \
  --number_of_steps=600000
