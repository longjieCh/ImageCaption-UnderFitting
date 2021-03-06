# encoding: utf-8
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
"""Evaluation utility for image Chinese captioning task."""
# __author__ = 'ZhengHe'
# python2.7
# python run_evaluations.py --submit=your_result_json_file --ref=reference_json_file

import sys
import argparse

reload(sys)
sys.setdefaultencoding('utf8')
from coco_caption.pycxtools.coco import COCO
from coco_caption.pycxevalcap.eval import COCOEvalCap


def compute_m1(json_predictions_file, reference_file, output_file):
    """Compute m1_score"""
    m1_score = {}
    m1_score['error'] = 0
    try:
        print >> sys.stderr, "loading reference file"
        coco = COCO(reference_file)
        print >> sys.stderr, "loading prediction file"
        coco_res = coco.loadRes(json_predictions_file)

        # create coco_eval object.
        print >> sys.stderr, "creating eval ops"
        coco_eval = COCOEvalCap(coco, coco_res)

        # evaluate results
        print >> sys.stderr, "evaluating"
        coco_eval.evaluate()
    except Exception as e:
        print e
        #m1_score['error'] = 1
    else:
        # print output evaluation scores
        for metric, score in coco_eval.eval.items():
            print 'Eval/%s: %.3f'%(metric, score)
            m1_score[metric] = score
        
        with open(output_file, 'w') as Fo:
            for imgId, imgRes in coco_eval.imgToEval.items():
                imgFilename = coco.imgToFilename[imgId]
                imgCaption = coco.imgToCaption[imgFilename]
                weight_B4 = 8.2
                weight_C = 2.4
                weight_M = 20.2
                weight_R = 12.6
                score = (weight_B4 * imgRes['Bleu_4'] + \
                        weight_C * imgRes['CIDEr'] + \
                        weight_M * imgRes['METEOR'] + \
                        weight_R * imgRes['ROUGE_L'] ) / 4.0
                print >> Fo, "\t".join([imgFilename, imgCaption.encode("utf8"), str(float(score))])
    return m1_score


def main():
    """The evaluator."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-submit", "--submit", type=str, required=True,
                        help=' JSON containing submit sentences.')
    parser.add_argument("-ref", "--ref", type=str,
                        help=' JSON references.')
    parser.add_argument("-output", "--output", type=str,
                        help=' CSV output (basename, caption, score).')
    args = parser.parse_args()

    json_predictions_file = args.submit
    reference_file = args.ref
    output_file = args.output
    print compute_m1(json_predictions_file, reference_file, output_file)


if __name__ == "__main__":
    main()
