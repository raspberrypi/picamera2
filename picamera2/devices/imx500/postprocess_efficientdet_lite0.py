"""
Efficientdet postprocessing

This code is based on:
https://github.com/google/automl/tree/master/efficientdet
"""

from typing import Tuple

import numpy as np

from picamera2.devices.imx500.postprocess import (
    BoxFormat, convert_to_ymin_xmin_ymax_xmax_format, nms)
from picamera2.devices.imx500.postprocess_yolov5 import coco80_to_coco91

default_box_variance = [1.0, 1.0, 1.0, 1.0]
default_aspect_ratios = [1.0, 2.0, 0.5]


def postprocess_efficientdet_lite0_detection(outputs: Tuple[np.ndarray, np.ndarray, np.ndarray],
                                             anchor_scale=3,
                                             min_level=3,
                                             max_level=7,
                                             box_variance=default_box_variance,
                                             model_input_shape=(320, 320),
                                             min_wh=2,
                                             max_wh=7680,
                                             conf_thres: float = 0.001,
                                             iou_thres: float = 0.65,
                                             max_nms_dets: int = 5000,
                                             max_out_dets: int = 1000):
    H, W = model_input_shape
    ############################################################
    # Box decoding
    ############################################################
    outputs_decoded = box_decoding_edetlite(output_annotations=outputs,
                                            H=H,
                                            W=W,
                                            anchor_scale=anchor_scale,
                                            min_level=min_level,
                                            max_level=max_level,
                                            box_variance=box_variance)

    classes = outputs[0]
    num_categories = classes.shape[-1]

    ############################################################
    # Post processing for each input image
    ############################################################
    # Note: outputs_decoded shape is [Batch,num_anchors*Detections,(4+1+num_categories)]
    post_processed_outputs = []
    for _, x in enumerate(outputs_decoded):
        # ----------------------------------------
        # Filter by score and width-height
        # ----------------------------------------
        scores = x[..., 4]
        wh = x[..., 2:4]
        valid_indexs = (scores > conf_thres) & ((wh > min_wh).any(1)) & ((wh < max_wh).any(1))
        x = x[valid_indexs]

        # ----------------------------------------
        # Taking Best class only
        # ----------------------------------------
        x[..., 5:] *= x[..., 4:5]  # compute confidence per class (class_score * object_score)
        conf = np.max(x[:, 5:], axis=1, keepdims=True)
        classes_id = np.argmax(x[:, 5:], axis=1, keepdims=True)

        # Change boxes format from [x_c,y_c,w,h] to [y_min,x_min,y_max,x_max]
        boxes = convert_to_ymin_xmin_ymax_xmax_format(x[..., :4], BoxFormat.XC_YC_W_H)
        x = np.concatenate((boxes, conf, classes_id), axis=1)[conf.reshape(-1) > conf_thres]

        # --------------------------- #
        # NMS
        # --------------------------- #
        x = x[np.argsort(-x[:, 4])[:max_nms_dets]]  # sort by confidence from high to low
        offset = x[..., 5:6] * np.maximum(H, W)
        boxes_offset, scores = x[..., :4] + offset, x[..., 4]  # boxes with offset by class
        valid_indexs = nms(dets=boxes_offset, scores=scores, iou_thres=iou_thres, max_out_dets=max_out_dets)
        x = x[valid_indexs]

        boxes = x[..., :4]

        # --------------------------- #
        # Classes process
        # --------------------------- #
        # convert classes from coco80 to coco91 to match labels
        classes = coco80_to_coco91(x[..., 5]) if num_categories == 80 else x[..., 5]
        classes -= 0

        # --------------------------- #
        # Scores
        # --------------------------- #
        scores = x[..., 4]

        # Add result
        post_processed_outputs.append({'boxes': boxes, 'classes': classes, 'scores': scores})

    return post_processed_outputs[0]['boxes'], post_processed_outputs[0]['scores'], post_processed_outputs[0]['classes']


def box_decoding_edetlite(output_annotations,
                          H=320,
                          W=320,
                          anchor_scale=3,
                          min_level=3,
                          max_level=7,
                          box_variance=default_box_variance):
    # -----------------------------------------------
    # EfficientDetLite detection post processing
    # -----------------------------------------------
    # Note: 'output_annotations' is expected to be a list of 2 feature maps with shapes:
    # [0] : [Batch,Detections,num_categories]
    # [1] : [Batch,Detections,4]
    classes = output_annotations[0]
    boxes = output_annotations[1]
    classes = 1 / (1 + np.exp(-classes))  # sigmoid
    scores = np.ones((*boxes.shape[:-1], 1))  # Add default object scores of 1.0

    # Combine tensors
    outputs = np.concatenate((boxes, scores, classes), axis=2)

    # Box decoding
    # Anchor boxes format: [y_min, x_min, y_max, x_max] normalized

    # Extract feature map sizes
    strides = [2 ** i for i in range(max_level + 1)]
    featmap_sizes = [(np.ceil(H / stride), np.ceil(W / stride)) for stride in strides]

    # Generate priors
    batch_size = outputs.shape[0]
    anchors = generate_anchors_EDETLITE(batch_size=batch_size,
                                        featmap_sizes=featmap_sizes,
                                        H=H,
                                        W=W,
                                        anchor_scale=anchor_scale,
                                        min_level=min_level,
                                        max_level=max_level)

    # Decode bboxes
    y_c_anchors = (anchors[..., 0:1] + anchors[..., 2:3]) / 2
    x_c_anchors = (anchors[..., 1:2] + anchors[..., 3:4]) / 2
    ha = anchors[..., 2:3] - anchors[..., 0:1]
    wa = anchors[..., 3:4] - anchors[..., 1:2]

    # Output Box format: [x_c, y_c, w, h]
    pred_boxes = outputs[..., :4]
    y_c = pred_boxes[..., 0:1] * box_variance[0] * ha + y_c_anchors
    x_c = pred_boxes[..., 1:2] * box_variance[1] * wa + x_c_anchors
    h = np.exp(pred_boxes[..., 2:3] * box_variance[2]) * ha
    w = np.exp(pred_boxes[..., 3:4] * box_variance[3]) * wa
    outputs[..., 0:1] = x_c
    outputs[..., 1:2] = y_c
    outputs[..., 2:3] = w
    outputs[..., 3:4] = h
    return outputs


def generate_anchors_EDETLITE(batch_size,
                              featmap_sizes,
                              H=320,
                              W=320,
                              anchor_scale=3,
                              min_level=3,
                              max_level=7,
                              aspect_ratios=default_aspect_ratios):
    """Generate configurations of anchor boxes."""
    anchor_scales = [anchor_scale] * (max_level - min_level + 1)
    num_scales = len(aspect_ratios)
    anchor_configs = {}
    for level in range(min_level, max_level + 1):
        anchor_configs[level] = []
        for scale_octave in range(num_scales):
            for aspect in aspect_ratios:
                anchor_configs[level].append(
                    ((featmap_sizes[0][0] / float(featmap_sizes[level][0]),
                      featmap_sizes[0][1] / float(featmap_sizes[level][1])),
                     scale_octave / float(num_scales), aspect,
                     anchor_scales[level - min_level]))

    """Generates multiscale anchor boxes."""
    boxes_all = []
    for _, configs in anchor_configs.items():
        boxes_level = []
        for config in configs:
            stride, octave_scale, aspect, anchor_scale = config
            base_anchor_size_x = anchor_scale * stride[1] * 2 ** octave_scale
            base_anchor_size_y = anchor_scale * stride[0] * 2 ** octave_scale
            if isinstance(aspect, list):
                aspect_x, aspect_y = aspect
            else:
                aspect_x = np.sqrt(aspect)
                aspect_y = 1.0 / aspect_x
            anchor_size_x_2 = base_anchor_size_x * aspect_x / 2.0
            anchor_size_y_2 = base_anchor_size_y * aspect_y / 2.0

            x = np.arange(stride[1] / 2, W, stride[1])
            y = np.arange(stride[0] / 2, H, stride[0])
            xv, yv = np.meshgrid(x, y)
            xv = xv.reshape(-1)
            yv = yv.reshape(-1)

            boxes = np.vstack((yv - anchor_size_y_2, xv - anchor_size_x_2,
                               yv + anchor_size_y_2, xv + anchor_size_x_2))
            boxes = np.swapaxes(boxes, 0, 1)
            boxes_level.append(np.expand_dims(boxes, axis=1))

        # concat anchors on the same level to the shape Batch x Detections x 4
        boxes_level = np.concatenate(boxes_level, axis=1).reshape([1, -1, 4])
        boxes_level = np.repeat(boxes_level, batch_size, axis=0)
        boxes_all.append(boxes_level)

    anchor_boxes = np.concatenate(boxes_all, axis=1)
    return anchor_boxes
