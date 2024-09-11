"""
Nanodet postprocessing

This code is based on:
https://github.com/RangiLyu/nanodet
"""

from typing import Tuple

import numpy as np

from picamera2.devices.imx500.postprocess import combined_nms, softmax


def postprocess_nanodet_detection(outputs,
                                  conf: float = 0.0,
                                  iou_thres: float = 0.65,
                                  max_out_dets: int = 300) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    reg_max = 7
    num_categories = 80
    classes = outputs[..., :num_categories]
    boxes = outputs[..., num_categories:]
    classes = 1 / (1 + np.exp(-classes))  # sigmoid

    # Extract feature map sizes
    strides = [8, 16, 32, 64]
    featmap_sizes = [(np.ceil(416 / stride), np.ceil(416 / stride)) for stride in strides]

    # Generate priors
    anchors = generate_anchors_NANODET(featmap_sizes, strides)

    # Decode bboxes
    batch = boxes.shape[0]
    x = np.reshape(boxes, newshape=(batch, -1, 4, reg_max + 1))
    x = softmax(x)
    x = np.matmul(x, np.arange(0, reg_max + 1, 1, dtype=np.float32))
    x = np.reshape(x, newshape=(batch, -1, 4))
    distances = x * anchors[..., 2, None]

    # Output Box format: [x_c, y_c, w, h]
    w = distances[..., 0:1] + distances[..., 2:3]
    h = distances[..., 1:2] + distances[..., 3:4]
    x_c = anchors[..., 0:1] - distances[..., 0:1] + w / 2
    y_c = anchors[..., 1:2] - distances[..., 1:2] + h / 2
    boxes = np.concatenate([x_c, y_c, w, h], axis=2)

    return combined_nms(boxes, classes, iou_thres, conf, max_out_dets)


def generate_anchors_NANODET(featmap_sizes, strides):
    anchors_list = []
    for i, stride in enumerate(strides):
        h, w = featmap_sizes[i]
        x_range = np.arange(w) * stride
        y_range = np.arange(h) * stride
        y, x = np.meshgrid(y_range, x_range)
        y = y.flatten()
        x = x.flatten()
        strides = np.ones_like(x) * stride
        anchors = np.stack([y, x, strides, strides], axis=-1)
        anchors = np.expand_dims(anchors, axis=0)
        anchors_list.append(anchors)
    return np.concatenate(anchors_list, axis=1)
