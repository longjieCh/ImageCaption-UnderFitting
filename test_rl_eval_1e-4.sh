#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

model_name="show_and_tell_advanced_model_attention_finetune_with_decay_da_rl_lr0.1"
num_processes=1
gpu_fraction=1
device=1
model=ShowAndTellAdvancedModel

MODEL_DIR="/home/share/limiao/ImageCaption/model/x39_rl_lr1e-4"
for ckpt in $(ls ${MODEL_DIR} | python ${DIR}/tools/every_n_step.py 20000); do 
  # the script directory
  VALIDATE_IMAGE_DIR="${DIR}/data/ai_challenger_caption_validation_20170910/caption_validation_images_20170910"
  VALIDATE_REFERENCE_FILE="${DIR}/data/ai_challenger_caption_validation_20170910/reference.json"

  CHECKPOINT_PATH="${MODEL_DIR}/model.ckpt-$ckpt"
  OUTPUT_DIR="${MODEL_DIR}/model.ckpt-${ckpt}.eval"

  mkdir $OUTPUT_DIR

  cd ${DIR}/im2txt
  if [ ! -f ${OUTPUT_DIR}/out.json ]; then
    CUDA_VISIBLE_DEVICES=$device python inference.py \
      --input_file_pattern="${VALIDATE_IMAGE_DIR}/${prefix}*.jpg" \
      --checkpoint_path=${CHECKPOINT_PATH} \
      --vocab_file=${DIR}/data/word_counts.txt \
      --output=${OUTPUT_DIR}/out.json \
      --model=${model} \
      --inception_return_tuple=True \
      --use_attention_wrapper=True \
      --attention_mechanism=BahdanauAttention \
      --num_lstm_layers=1 \
      --support_ingraph=True \
      --gpu_memory_fraction=$gpu_fraction
    echo output saved to ${OUTPUT_DIR}/out.json
  fi

  if [ ! -f ${OUTPUT_DIR}/out.eval ]; then
    python ${DIR}/tools/eval/run_evaluations.py --submit ${OUTPUT_DIR}/out.json --ref $VALIDATE_REFERENCE_FILE | tee ${OUTPUT_DIR}/out.eval | grep ^Eval
    echo eval result saved to ${OUTPUT_DIR}/out.eval
  fi
done
