"""
Yolov5 postprocessing

This code is based on:
https://github.com/ultralytics/ultralytics
"""
from typing import List

import cv2
import numpy as np

from picamera2.devices.imx500.postprocess import (
    BoxFormat, convert_to_ymin_xmin_ymax_xmax_format, nms)

default_anchors = [[10, 13, 16, 30, 33, 23],
                   [30, 61, 62, 45, 59, 119],
                   [116, 90, 156, 198, 373, 326]]
default_strides = [8, 16, 32]


def postprocess_yolov5_detection(outputs: List[np.ndarray],
                                 model_input_shape=(640, 640),
                                 num_categories=80,
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
    outputs_decoded = box_decoding_yolov5n(tensors=outputs, num_categories=num_categories, H=H, W=W)

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
        classes -= 1

        # --------------------------- #
        # Scores
        # --------------------------- #
        scores = x[..., 4]

        # Add result
        post_processed_outputs.append({'boxes': boxes, 'classes': classes, 'scores': scores})

    return post_processed_outputs[0]['boxes'], post_processed_outputs[0]['scores'], post_processed_outputs[0]['classes']


def box_decoding_yolov5n(tensors,
                         num_categories=80,
                         H=640,
                         W=640,
                         anchors=default_anchors,
                         strides=default_strides):
    # Tensors box format: [x_c, y_c, w, h]
    no = num_categories + 5  # number of outputs per anchor
    nl = len(anchors)  # number of detection layers
    na = len(anchors[0]) // 2  # number of anchors
    anchor_grid = np.reshape(np.array(anchors), [nl, 1, -1, 1, 2])
    anchor_grid = anchor_grid.astype(np.float32)
    z = []
    for i in range(nl):
        ny, nx = H // strides[i], W // strides[i]
        xv, yv = np.meshgrid(np.arange(nx), np.arange(ny))
        grid = np.reshape(np.stack([xv, yv], 2), [1, 1, ny * nx, 2]).astype(np.float32)

        y = tensors[i]
        y = np.transpose(y, [0, 2, 1, 3])
        xy = (y[..., 0:2] * 2 - 0.5 + grid) * strides[i]  # xy
        wh = (y[..., 2:4] * 2) ** 2 * anchor_grid[i]

        # Output box format: [x_c, y_c, w, h]
        y = np.concatenate([xy, wh, y[..., 4:]], -1)
        z.append(np.reshape(y, [-1, na * ny * nx, no]))

    return np.concatenate(z, 1)


# same as in preprocess but differs in h/w location
def scale_boxes(boxes: np.ndarray, h_image: int, w_image: int, h_model: int, w_model: int,
                preserve_aspect_ratio: bool) -> np.ndarray:
    """
    Scale and offset bounding boxes based on model output size and original image size.

    Args:
        boxes (numpy.ndarray): Array of bounding boxes in format [y_min, x_min, y_max, x_max].
        h_image (int): Original image height.
        w_image (int): Original image width.
        h_model (int): Model output height.
        w_model (int): Model output width.
        preserve_aspect_ratio (bool): Whether to preserve image aspect ratio during scaling

    Returns:
        numpy.ndarray: Scaled and offset bounding boxes.
    """
    deltaH, deltaW = 0, 0
    H, W = h_model, w_model
    scale_H, scale_W = h_image / H, w_image / W

    if preserve_aspect_ratio:
        scale_H = scale_W = max(h_image / H, w_image / W)
        H_tag = int(np.round(h_image / scale_H))
        W_tag = int(np.round(w_image / scale_W))
        deltaH, deltaW = int((H - H_tag) / 2), int((W - W_tag) / 2)

    # Scale and offset boxes
    boxes[..., 0] = (boxes[..., 0] - deltaH) * scale_H
    boxes[..., 1] = (boxes[..., 1] - deltaW) * scale_W
    boxes[..., 2] = (boxes[..., 2] - deltaH) * scale_H
    boxes[..., 3] = (boxes[..., 3] - deltaW) * scale_W

    # Clip boxes
    boxes = clip_boxes(boxes, h_image, w_image)

    return boxes


# same as in preprocess but differs in h/w location
def clip_boxes(boxes: np.ndarray, h: int, w: int) -> np.ndarray:
    """
    Clip bounding boxes to stay within the image boundaries.

    Args:
        boxes (numpy.ndarray): Array of bounding boxes in format [y_min, x_min, y_max, x_max].
        h (int): Height of the image.
        w (int): Width of the image.

    Returns:
        numpy.ndarray: Clipped bounding boxes.
    """
    boxes[..., 0] = np.clip(boxes[..., 0], a_min=0, a_max=h)
    boxes[..., 1] = np.clip(boxes[..., 1], a_min=0, a_max=w)
    boxes[..., 2] = np.clip(boxes[..., 2], a_min=0, a_max=h)
    boxes[..., 3] = np.clip(boxes[..., 3], a_min=0, a_max=w)
    return boxes


def _normalize_coordinates(boxes, orig_width, orig_height, boxes_format):
    """
    Gets boxes in the original images values and normalize them to be between 0 to 1

    :param boxes:
    :param orig_width: original image width
    :param orig_height: original image height
    :param boxes_format: if the boxes are in XMIN_YMIN_W_H or YMIM_XMIN_YMAX_XMAX format
    :return:
    """
    if len(boxes) == 0:
        return boxes
    elif _are_boxes_normalized(boxes):
        return boxes
    boxes[:, 0] = np.divide(boxes[:, 0], orig_height)
    boxes[:, 1] = np.divide(boxes[:, 1], orig_width)
    boxes[:, 2] = np.divide(boxes[:, 2], orig_height)
    boxes[:, 3] = np.divide(boxes[:, 3], orig_width)
    return boxes


def _are_boxes_normalized(boxes):
    if len(boxes) == 0:
        return True  # it doesn't matter
    if max(boxes[0]) > 1:
        return False
    return True


def apply_normalization(boxes, orig_width, orig_height, boxes_format):
    if _are_boxes_normalized(boxes):
        return boxes
    return _normalize_coordinates(boxes, orig_width, orig_height, boxes_format)


# Locate at tutorials
def coco80_to_coco91(x):  # converts 80-index to 91-index
    coco91Indexs = np.array(
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 27, 28, 31, 32, 33, 34,
         35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62,
         63, 64, 65, 67, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 84, 85, 86, 87, 88, 89, 90])

    return coco91Indexs[x.astype(np.int32)]


def yolov5n_preprocess(img):
    # AspectPreservingResizeWithPad
    new_height = 640
    new_width = 640
    pad_value = 114
    resize_method = 3  # area
    resize_ratio = max(img.shape[0] / new_height, img.shape[1] / new_width)
    height_tag = int(np.round(img.shape[0] / resize_ratio))
    width_tag = int(np.round(img.shape[1] / resize_ratio))
    pad_values = ((int((new_height - height_tag) / 2), int((new_height - height_tag) / 2 + 0.5)),
                  (int((new_width - width_tag) / 2), int((new_width - width_tag) / 2 + 0.5)),
                  (0, 0))

    resized_img = cv2.resize(img, (width_tag, height_tag), interpolation=resize_method)
    padded_img = np.pad(resized_img, pad_values, constant_values=pad_value)

    # Normalize
    mean = 0
    std = 255
    normalized_img = (padded_img - mean) / std

    return normalized_img
