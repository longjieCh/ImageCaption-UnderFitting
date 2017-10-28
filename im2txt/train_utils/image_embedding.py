# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
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
# ==============================================================================

"""Image embedding ops."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


import tensorflow as tf

from tensorflow.contrib.slim.python.slim.nets.inception_v3 import inception_v3_base

slim = tf.contrib.slim


def inception_v3(images,
                 trainable=True,
                 is_training=True,
                 weight_decay=0.00004,
                 stddev=0.1,
                 dropout_keep_prob=0.8,
                 use_batch_norm=True,
                 batch_norm_params=None,
                 add_summaries=True,
                 scope="InceptionV3",
                 use_box=False,
                 inception_return_tuple=False,
                 yet_another_inception=False):
  """Builds an Inception V3 subgraph for image embeddings.

  Args:
    images: A float32 Tensor of shape [batch, height, width, channels].
    trainable: Whether the inception submodel should be trainable or not.
    is_training: Boolean indicating training mode or not.
    weight_decay: Coefficient for weight regularization.
    stddev: The standard deviation of the trunctated normal weight initializer.
    dropout_keep_prob: Dropout keep probability.
    use_batch_norm: Whether to use batch normalization.
    batch_norm_params: Parameters for batch normalization. See
      tf.contrib.layers.batch_norm for details.
    add_summaries: Whether to add activation summaries.
    use_box: Whether to use position information.
    scope: Optional Variable scope.

  Returns:
    end_points: A dictionary of activations from inception_v3 layers.
  """
  # Only consider the inception model to be in training mode if it's trainable.
  is_inception_model_training = trainable and is_training

  if use_batch_norm:
    # Default parameters for batch normalization.
    if not batch_norm_params:
      batch_norm_params = {
          "is_training": is_inception_model_training,
          "trainable": trainable,
          # Decay for the moving averages.
          "decay": 0.9997,
          # Epsilon to prevent 0s in variance.
          "epsilon": 0.001,
          # Collection containing the moving mean and moving variance.
          "variables_collections": {
              "beta": None,
              "gamma": None,
              "moving_mean": ["moving_vars"],
              "moving_variance": ["moving_vars"],
          }
      }
  else:
    batch_norm_params = None

  if trainable:
    weights_regularizer = tf.contrib.layers.l2_regularizer(weight_decay)
  else:
    weights_regularizer = None

  with tf.variable_scope(scope, "InceptionV3", [images]) as scope:
    with slim.arg_scope(
        [slim.conv2d, slim.fully_connected],
        weights_regularizer=weights_regularizer,
        trainable=trainable):
      with slim.arg_scope(
          [slim.conv2d],
          weights_initializer=tf.truncated_normal_initializer(stddev=stddev),
          activation_fn=tf.nn.relu,
          normalizer_fn=slim.batch_norm,
          normalizer_params=batch_norm_params):
        net, end_points = inception_v3_base(images, scope=scope)
        with tf.variable_scope("logits"):
          shape = net.get_shape()
          print(net.get_shape().as_list())
          if inception_return_tuple:
            original_net = tf.reshape(net, [tf.cast(shape[0],tf.int32), tf.cast(shape[1]*shape[2],tf.int32), tf.cast(shape[3],tf.int32)])
            net = slim.avg_pool2d(net, shape[1:3], padding="VALID", scope="pool")
          elif use_box:
            net = tf.reshape(net, [tf.cast(shape[0],tf.int32), tf.cast(shape[1]*shape[2],tf.int32), tf.cast(shape[3],tf.int32)])
          else:
            net = slim.avg_pool2d(net, shape[1:3], padding="VALID", scope="pool")

          net = slim.dropout(
              net,
              keep_prob=dropout_keep_prob,
              is_training=is_inception_model_training,
              scope="dropout")
          net = slim.flatten(net, scope="flatten")

  # Add summaries.
  if add_summaries:
    for v in end_points.values():
      tf.contrib.layers.summaries.summarize_activation(v)

  if yet_another_inception:
    ya_scope = "ya_" + scope
    with tf.variable_scope(ya_scope, "InceptionV3", [images]) as scope:
      with slim.arg_scope(
          [slim.conv2d, slim.fully_connected],
          weights_regularizer=weights_regularizer,
          trainable=trainable):
        with slim.arg_scope(
            [slim.conv2d],
            weights_initializer=tf.truncated_normal_initializer(stddev=stddev),
            activation_fn=tf.nn.relu,
            normalizer_fn=slim.batch_norm,
            normalizer_params=batch_norm_params):
          ya_net, ya_end_points = inception_v3_base(images, scope=scope)
          with tf.variable_scope("logits"):
            ya_shape = ya_net.get_shape()
            print(ya_net.get_shape().as_list())
            if inception_return_tuple:
              ya_original_net = tf.reshape(ya_net, [tf.cast(ya_shape[0],tf.int32), tf.cast(ya_shape[1]*shape[2],tf.int32), tf.cast(ya_shape[3],tf.int32)])
              ya_net = slim.avg_pool2d(ya_net, ya_shape[1:3], padding="VALID", scope="pool")
            elif use_box:
              ya_net = tf.reshape(ya_net, [tf.cast(ya_shape[0],tf.int32), tf.cast(ya_shape[1]*ya_shape[2],tf.int32), tf.cast(ya_shape[3],tf.int32)])
            else:
              ya_net = slim.avg_pool2d(ya_net, ya_shape[1:3], padding="VALID", scope="pool")

            ya_net = slim.dropout(
                ya_net,
                keep_prob=dropout_keep_prob,
                is_training=is_inception_model_training,
                scope="dropout")
            ya_net = slim.flatten(ya_net, scope="flatten")

    # Add summaries.
    if add_summaries:
      for v in ya_end_points.values():
        tf.contrib.layers.summaries.summarize_activation(v)

  if yet_another_inception:
    if inception_return_tuple:
      return net, original_net, ya_net, ya_original_net
    else:
      return net, ya_net
  else:
    if inception_return_tuple:
      return net, original_net
    else:
      return net
