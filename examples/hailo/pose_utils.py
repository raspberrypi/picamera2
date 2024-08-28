import numpy as np

kwargs = {
    'classes': 1,
    'nms_max_output_per_class': 300,
    'anchors': {'regression_length': 15, 'strides': [8, 16, 32]},
    'score_threshold': 0.001,
    'nms_iou_thresh': 0.7,
    'meta_arch': 'nanodet_v8',
    'device_pre_post_layers': None
}


def postproc_yolov8_pose(num_of_classes, raw_detections, img_size):
    # The input is a dictionary of outputs for each layer. For each layer we may have:
    #     A single numpy array, if batching was not used.
    #     A list of numpy arrays, when a batch size was specified.
    # We convert the "list" into an extra numpy dimensions, which is what the code here expects.
    for layer, output in raw_detections.items():
        if not isinstance(output, list):
            raw_detections[layer] = np.expand_dims(output, axis=0)
        elif len(output) == 1:
            raw_detections[layer] = np.expand_dims(output[0], axis=0)
        else:
            raise RuntimeError("Pose post-processing only supports a batch size of 1")

    kwargs['img_dims'] = img_size
    raw_detections_keys = list(raw_detections.keys())
    layer_from_shape: dict = {raw_detections[key].shape: key for key in raw_detections_keys}

    detection_output_channels = (kwargs['anchors']['regression_length'] + 1) * 4  # (regression length + 1) * num_coordinates
    keypoints = 51

    # The following assumes that the batch size is 1:
    endnodes = [raw_detections[layer_from_shape[1, 20, 20, detection_output_channels]],
                raw_detections[layer_from_shape[1, 20, 20, num_of_classes]],
                raw_detections[layer_from_shape[1, 20, 20, keypoints]],
                raw_detections[layer_from_shape[1, 40, 40, detection_output_channels]],
                raw_detections[layer_from_shape[1, 40, 40, num_of_classes]],
                raw_detections[layer_from_shape[1, 40, 40, keypoints]],
                raw_detections[layer_from_shape[1, 80, 80, detection_output_channels]],
                raw_detections[layer_from_shape[1, 80, 80, num_of_classes]],
                raw_detections[layer_from_shape[1, 80, 80, keypoints]]]

    predictions_dict = yolov8_pose_estimation_postprocess(endnodes, **kwargs)

    return predictions_dict


# ---------------- Architecture functions ----------------- #

def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def _softmax(x):
    return np.exp(x) / np.expand_dims(np.sum(np.exp(x), axis=-1), axis=-1)


def max(a, b):
    return a if a >= b else b


def min(a, b):
    return a if a <= b else b


def nms(dets, thresh):
    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]
    scores = dets[:, 4]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = np.argsort(scores)[::-1]

    ndets = dets.shape[0]
    suppressed = np.zeros((ndets), dtype=int)

    for _i in range(ndets):
        i = order[_i]
        if suppressed[i] == 1:
            continue
        ix1 = x1[i]
        iy1 = y1[i]
        ix2 = x2[i]
        iy2 = y2[i]
        iarea = areas[i]
        for _j in range(_i + 1, ndets):
            j = order[_j]
            if suppressed[j] == 1:
                continue
            xx1 = max(ix1, x1[j])
            yy1 = max(iy1, y1[j])
            xx2 = min(ix2, x2[j])
            yy2 = min(iy2, y2[j])
            w = max(0.0, xx2 - xx1 + 1)
            h = max(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (iarea + areas[j] - inter)
            if ovr >= thresh:
                suppressed[j] = 1

    return np.where(suppressed == 0)[0]


def _yolov8_decoding(raw_boxes, raw_kpts, strides, image_dims, reg_max):
    boxes = None
    decoded_kpts = None

    for box_distribute, kpts, stride, _ in zip(raw_boxes, raw_kpts, strides, np.arange(3)):
        # create grid
        shape = [int(x / stride) for x in image_dims]
        grid_x = np.arange(shape[1]) + 0.5
        grid_y = np.arange(shape[0]) + 0.5
        grid_x, grid_y = np.meshgrid(grid_x, grid_y)
        ct_row = grid_y.flatten() * stride
        ct_col = grid_x.flatten() * stride
        center = np.stack((ct_col, ct_row, ct_col, ct_row), axis=1)

        # box distribution to distance
        reg_range = np.arange(reg_max + 1)
        box_distribute = np.reshape(
            box_distribute, (-1, box_distribute.shape[1] * box_distribute.shape[2], 4, reg_max + 1))
        box_distance = _softmax(box_distribute)
        box_distance = box_distance * np.reshape(reg_range, (1, 1, 1, -1))
        box_distance = np.sum(box_distance, axis=-1)
        box_distance = box_distance * stride

        # decode box
        box_distance = np.concatenate([box_distance[:, :, :2] * (-1), box_distance[:, :, 2:]], axis=-1)
        decode_box = np.expand_dims(center, axis=0) + box_distance

        xmin = decode_box[:, :, 0]
        ymin = decode_box[:, :, 1]
        xmax = decode_box[:, :, 2]
        ymax = decode_box[:, :, 3]
        decode_box = np.transpose([xmin, ymin, xmax, ymax], [1, 2, 0])

        xywh_box = np.transpose([(xmin + xmax) / 2, (ymin + ymax) / 2, xmax - xmin, ymax - ymin], [1, 2, 0])
        boxes = xywh_box if boxes is None else np.concatenate([boxes, xywh_box], axis=1)

        # kpts decoding
        kpts[..., :2] *= 2
        kpts[..., :2] = stride * (kpts[..., :2] - 0.5) + np.expand_dims(center[..., :2], axis=1)

        decoded_kpts = kpts if decoded_kpts is None else np.concatenate([decoded_kpts, kpts], axis=1)

    return boxes, decoded_kpts


def xywh2xyxy(x):
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def non_max_suppression(prediction, conf_thres=0.1, iou_thres=0.45,
                        max_det=100, n_kpts=17):
    """Non-Maximum Suppression (NMS) on inference results to reject overlapping detections.

    Args:
        prediction: numpy.ndarray with shape (batch_size, num_proposals, 56)
        conf_thres: confidence threshold for NMS
        iou_thres: IoU threshold for NMS
        max_det: Maximal number of detections to keep after NMS
        nm: Number of masks
        multi_label: Consider only best class per proposal or all conf_thresh passing proposals

    Returns:
        A list of per image detections, where each is a dictionary with the following structure:
        {
        'detection_boxes':  numpy.ndarray with shape (num_detections, 4),
        'keypoints':        numpy.ndarray with shape (num_detections, 17, 3),
        'detection_scores': numpy.ndarray with shape (num_detections, 1),
        'num_detections':   int
        }
    """
    assert 0 <= conf_thres <= 1, \
        f'Invalid Confidence threshold {conf_thres}, valid values are between 0.0 and 1.0'
    assert 0 <= iou_thres <= 1, \
        f'Invalid IoU threshold {iou_thres}, valid values are between 0.0 and 1.0'

    nc = prediction.shape[2] - n_kpts * 3 - 4  # number of classes
    xc = prediction[..., 4] > conf_thres  # candidates

    # max_wh = 7680  # (pixels) maximum box width and height
    ki = 4 + nc  # keypoints start index
    output = []
    for xi, x in enumerate(prediction):  # image index, image inference
        x = x[xc[xi]]
        # If none remain process next image
        if not x.shape[0]:
            output.append({'bboxes': np.zeros((0, 4)),
                           'keypoints': np.zeros((0, n_kpts, 3)),
                           'scores': np.zeros((0)),
                           'num_detections': 0})
            continue

        # (center_x, center_y, width, height) to (x1, y1, x2, y2)
        boxes = xywh2xyxy(x[:, :4])
        kpts = x[:, ki:]

        conf = np.expand_dims(x[:, 4:ki].max(1), 1)
        j = np.expand_dims(x[:, 4:ki].argmax(1), 1).astype(np.float32)

        keep = np.squeeze(conf, 1) > conf_thres
        x = np.concatenate((boxes, conf, j, kpts), 1)[keep]

        # sort by confidence
        x = x[x[:, 4].argsort()[::-1]]

        boxes = x[:, :4]
        conf = x[:, 4:5]
        preds = np.hstack([boxes.astype(np.float32), conf.astype(np.float32)])

        keep = nms(preds, iou_thres)
        if keep.shape[0] > max_det:
            keep = keep[:max_det]

        out = x[keep]
        scores = out[:, 4]
        boxes = out[:, :4]
        kpts = out[:, 6:]
        kpts = np.reshape(kpts, (-1, n_kpts, 3))

        out = {'bboxes': boxes,
               'keypoints': kpts,
               'scores': scores,
               'num_detections': int(scores.shape[0])}

        output.append(out)
    return output


def yolov8_pose_estimation_postprocess(endnodes, **kwargs):
    """Decode and run NMS on Yolov8 pose estimation output.

    endnodes is a list of 10 tensors:
        endnodes[0]:  bbox output with shapes (BS, 20, 20, 64)
        endnodes[1]:  scores output with shapes (BS, 20, 20, 80)
        endnodes[2]:  keypoints output with shapes (BS, 20, 20, 51)
        endnodes[3]:  bbox output with shapes (BS, 40, 40, 64)
        endnodes[4]:  scores output with shapes (BS, 40, 40, 80)
        endnodes[5]:  keypoints output with shapes (BS, 40, 40, 51)
        endnodes[6]:  bbox output with shapes (BS, 80, 80, 64)
        endnodes[7]:  scores output with shapes (BS, 80, 80, 80)
        endnodes[8]:  keypoints output with shapes (BS, 80, 80, 51)

    Returns:
        A list of per image detections, where each is a dictionary with the following structure:
        {
        'detection_boxes':   numpy.ndarray with shape (num_detections, 4),
        'keypoints':         numpy.ndarray with shape (num_detections, 3),
        'detection_classes': numpy.ndarray with shape (num_detections, 80),
        'detection_scores':  numpy.ndarray with shape (num_detections, 80)
        }
    """
    batch_size = endnodes[0].shape[0]
    num_classes = kwargs['classes']  # always 1
    max_detections = kwargs['nms_max_output_per_class']
    strides = kwargs['anchors']['strides'][::-1]
    image_dims = tuple(kwargs['img_dims'])
    reg_max = kwargs['anchors']['regression_length']
    raw_boxes = endnodes[:7:3]
    scores = [np.reshape(s, (-1, s.shape[1] * s.shape[2], num_classes)) for s in endnodes[1:8:3]]
    scores = np.concatenate(scores, axis=1)
    kpts = [np.reshape(c, (-1, c.shape[1] * c.shape[2], 17, 3)) for c in endnodes[2:9:3]]
    decoded_boxes, decoded_kpts = _yolov8_decoding(raw_boxes, kpts, strides, image_dims, reg_max)
    score_thres = kwargs['score_threshold']
    iou_thres = kwargs['nms_iou_thresh']

    decoded_kpts = np.reshape(decoded_kpts, (batch_size, -1, 51))
    predictions = np.concatenate([decoded_boxes, scores, decoded_kpts], axis=2)
    nms_res = non_max_suppression(predictions, conf_thres=score_thres, iou_thres=iou_thres, max_det=max_detections)
    output = {}
    output['bboxes'] = np.zeros((batch_size, max_detections, 4))
    output['keypoints'] = np.zeros((batch_size, max_detections, 17, 2))
    output['joint_scores'] = np.zeros((batch_size, max_detections, 17, 1))
    output['scores'] = np.zeros((batch_size, max_detections, 1))
    for b in range(batch_size):
        output['bboxes'][b, :nms_res[b]['num_detections']] = nms_res[b]['bboxes']
        output['keypoints'][b, :nms_res[b]['num_detections']] = nms_res[b]['keypoints'][..., :2]
        output['joint_scores'][b, :nms_res[b]['num_detections'], ..., 0] = _sigmoid(nms_res[b]['keypoints'][..., 2])
        output['scores'][b, :nms_res[b]['num_detections'], ..., 0] = nms_res[b]['scores']
    return output
