import argparse

import cv2
import numpy as np

from picamera2 import CompletedRequest, MappedArray, Picamera2
from picamera2.devices import IMX500
from picamera2.devices.imx500.postprocess import (COCODrawer, scale_boxes,
                                                  scale_coords)
from picamera2.devices.imx500.postprocess_yolov8 import \
    postprocess_yolov8_keypoints

last_boxes = None
last_scores = None
last_keypoints = None


def ai_output_tensor_parse(metadata: dict):
    """Parse the output tensor into a number of detected objects, scaled to the ISP out."""
    global last_boxes, last_scores, last_keypoints
    np_outputs = imx500.get_outputs(metadata=metadata, add_batch=True)
    if np_outputs is not None:
        boxes, last_scores, keypoints = postprocess_yolov8_keypoints(outputs=np_outputs,
                                                                     conf=args.box_min_confidence,
                                                                     iou_thres=args.iou_threshold,
                                                                     max_out_dets=args.max_out_dets)
        keypoints = np.reshape(keypoints, [keypoints.shape[0], 17, 3])
        last_keypoints = scale_coords(keypoints, 1, 1, 640, 640, True)
        last_boxes = scale_boxes(boxes, 1, 1, 640, 640, True, False)
    return last_boxes, last_scores, last_keypoints


def ai_output_tensor_draw(request: CompletedRequest, results, stream='main'):
    """Draw the detections for this request onto the ISP output."""
    if not results:
        return

    boxes, scores, keypoints = results
    with MappedArray(request, stream) as m:
        if boxes is not None and len(boxes) > 0:
            drawer.annotate_image(m.array, boxes, scores,
                                  np.zeros(scores.shape), keypoints, args.box_min_confidence,
                                  args.keypoint_min_confidence,
                                  request.get_metadata(), picam2, stream)
        b = imx500.get_roi_scaled(request)
        cv2.putText(m.array, "ROI", (b.x + 5, b.y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.rectangle(m.array, (b.x, b.y), (b.x + b.width, b.y + b.height), (255, 0, 0, 0))


def picamera2_pre_callback(request: CompletedRequest):
    """Analyse the detected objects in the output tensor and draw them on the main output image."""
    ai_output_tensor_draw(request, last_results)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="/usr/share/imx500-models/imx500_network_posenet.rpk",
                        help="Path of the model")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--box-min-confidence", type=float,
                        default=0.3, help="Confidence threshold for bounding box predictions")
    parser.add_argument("--keypoint-min-confidence", type=float,
                        default=0.3, help="Minimum confidence required to keypoint")
    parser.add_argument("--iou-threshold", type=float, default=0.7,
                        help="IoU (Intersection over Union) threshold for Non-Maximum Suppression (NMS)")
    parser.add_argument("--max-out-dets", type=int, default=300,
                        help="Maximum number of output detections to keep after NMS")
    parser.add_argument("--labels", type=str, default="assets/coco_labels.txt",
                        help="Path to the labels file")
    return parser.parse_args()


def get_drawer():
    with open(args.labels, "r") as f:
        categories = f.read().split("\n")
    categories = [c for c in categories if c and c != "-"]
    return COCODrawer(categories, imx500)


if __name__ == "__main__":
    args = get_args()

    # This must be called before instantiation of Picamera2
    imx500 = IMX500(args.model)

    last_results = None

    drawer = get_drawer()

    picam2 = Picamera2(imx500.camera_num)
    config = picam2.create_preview_configuration(controls={'FrameRate': args.fps}, buffer_count=16)
    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=True)
    imx500.set_auto_aspect_ratio()
    picam2.pre_callback = picamera2_pre_callback

    while True:
        last_results = ai_output_tensor_parse(picam2.capture_metadata())
