import argparse
import time
from functools import lru_cache

import numpy as np
import cv2

from picamera2.devices import IMX500
from picamera2 import Picamera2, CompletedRequest, MappedArray
from picamera2.devices.imx500.postprocess import COCODrawer, scale_boxes
from picamera2.devices.imx500.postprocess_yolov8 import postprocess_yolov8_inst_seg, process_masks

COLOURS = np.loadtxt("assets/colours.txt")


def create_and_draw_masks(request: CompletedRequest):
    """Create masks from the output tensor and draw them on the main output image."""
    boxes, scores, classes, masks = create_masks(request)
    ai_output_tensor_draw(request, boxes, scores, classes, masks)


def create_masks(request: CompletedRequest):
    """Create masks from the output tensor, scaled to the ISP out."""
    np_outputs = imx500.get_outputs(metadata=request.get_metadata(), add_batch=True)
    if np_outputs is None:
        return None, None, None, None
    boxes, scores, classes, masks = postprocess_yolov8_inst_seg(outputs=np_outputs,
                                                                conf=args.score_threshold,
                                                                iou_thres=args.iou_threshold,
                                                                max_out_dets=args.max_out_dets)
    if len(scores) == 0:
        return None, None, None, None

    input_w, input_h = imx500.get_input_size()
    h_mask, w_mask = masks.shape[1], masks.shape[2]
    boxes_scale_down = scale_boxes(boxes.copy(), h_mask, w_mask, input_h, input_w, False, False)
    roi = imx500.get_roi_scaled(request)
    isp_output_size = imx500.get_isp_output_size(request)
    masks = process_masks(masks, boxes_scale_down, roi, isp_output_size)
    boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False, False)
    return boxes, scores, classes, masks


def ai_output_tensor_draw(request: CompletedRequest, boxes, scores, classes, masks, stream='main'):
    """Draw the detections for this request onto the ISP output."""
    with MappedArray(request, stream) as m:
        if scores is not None and len(scores) > 0:
            labels = get_labels()
            drawer.overlay_masks(picam2=picam2, masks=masks, scores=scores, colors=COLOURS,
                                 score_threshold=args.score_threshold,
                                 mask_threshold=args.mask_threshold)
            for score, box, c in zip(scores, boxes, classes):
                b = imx500.convert_inference_coords(box, request.get_metadata(), picam2)
                label = f"{labels[int(c)]} ({score:.2f})"
                cv2.putText(m.array, label, (b.x + 5, b.y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                cv2.rectangle(m.array, (b.x, b.y), (b.x + b.width, b.y + b.height), (0, 0, 255, 0))
        b = imx500.get_roi_scaled(request)
        cv2.putText(m.array, "ROI", (b.x + 5, b.y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.rectangle(m.array, (b.x, b.y), (b.x + b.width, b.y + b.height), (255, 0, 0, 0))


@lru_cache
def get_labels():
    """ get list of labels """
    with open(args.labels, "r") as f:
        labels = f.read().split("\n")
    labels = [c for c in labels if c and c != "-"]
    return labels


def get_drawer():
    """ get drawer object """
    return COCODrawer(get_labels(), imx500)


def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="Path of the model")
    parser.add_argument("--fps", type=int, default=5, help="Frames per second")
    parser.add_argument("--score-threshold", type=float, default=0.1, help="Detection threshold")
    parser.add_argument("--mask-threshold", type=float, default=0.5, help="Mask threshold")
    parser.add_argument("--iou-threshold", type=float, default=0.7,
                        help="IoU (Intersection over Union) threshold for Non-Maximum Suppression (NMS)")
    parser.add_argument("--max-out-dets", type=int, default=7,
                        help="Maximum number of output detections to keep after NMS")
    parser.add_argument("--labels", type=str, default="assets/coco_labels.txt",
                        help="Path to the labels file")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()

    # This must be called before instantiation of Picamera2
    imx500 = IMX500(args.model)
    drawer = get_drawer()

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(controls={'FrameRate': args.fps}, buffer_count=28)

    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=True)
    imx500.set_auto_aspect_ratio()
    picam2.pre_callback = create_and_draw_masks

    while True:
        time.sleep(0.5)
