#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

model_name="ranker_pointwise_baseline_model"
num_processes=1
gpu_fraction=1.0
device=0
image_model=InceptionV3Model
text_model=LstmModel
match_model=MlpModel
TFRECORD_DIR="${DIR}/data/Ranker_TFRecord_data/d706a6d0dafbc3e2d660cca2f5d5da50b11f181c"

MODEL_DIR="${DIR}/model/${model_name}"
#ckpt=160305
ckpt=140882

CHECKPOINT_PATH="${MODEL_DIR}/model.ckpt-$ckpt"
OUTPUT_DIR="${MODEL_DIR}/model.ckpt-${ckpt}.inference"

mkdir $OUTPUT_DIR

cd ${DIR}/ranker

if [ ! -f ${OUTPUT_DIR}/out.csv ]; then
  CUDA_VISIBLE_DEVICES=$device python inference.py \
    --input_file_pattern="${TFRECORD_DIR}/rankertest-TEST-*.tfrecord" \
    --lines_per_image=21 \
    --batch_size=21 \
    --num_readers=1 \
    --checkpoint_path=${CHECKPOINT_PATH} \
    --vocab_file=${DIR}/data/word_counts.txt \
    --output=${OUTPUT_DIR}/out.csv \
    --model=${model} \
    --image_model=${image_model} \
    --text_model=${text_model} \
    --match_model=${match_model} \
    --mlp_num_layers=2 \
    --mlp_num_units="512,256" \
    --mlp_type_activation="sigmoid" \
    --lstm_cell_type="highway" \
    --num_lstm_layers=2 \
    --num_steps=30000
fi

if [ ! -f ${OUTPUT_DIR}/out.json ]; then
  cat ${OUTPUT_DIR}/out.csv | python ${DIR}/scripts/ranker_convert_csv_to_oracle_prediction.py > ${OUTPUT_DIR}/out.json
  echo output saved to ${OUTPUT_DIR}/out.json
fi

