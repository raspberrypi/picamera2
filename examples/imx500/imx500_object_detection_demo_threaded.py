import argparse
import queue
import threading
from functools import lru_cache
import cv2
import numpy as np

from picamera2.devices import IMX500
from picamera2 import MappedArray, Picamera2

from picamera2.devices.imx500 import postprocess_nanodet_detection
from picamera2.devices.imx500 import postprocess_yolov5_detection
from picamera2.devices.imx500 import postprocess_yolov8_detection
from picamera2.devices.imx500 import postprocess_efficientdet_lite0_detection

last_detections = []


class Detection:
    def __init__(self, coords, category, conf, metadata):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        obj_scaled = imx500.convert_inference_coords(coords, metadata, picam2)
        self.box = (obj_scaled.x, obj_scaled.y, obj_scaled.width, obj_scaled.height)


def parse_detections(metadata: dict):
    """Parse the output tensor into a number of detected objects, scaled to the ISP out."""
    global last_detections
    bbox_normalization = args.bbox_normalization
    threshold = args.threshold
    iou = args.iou
    max_detections = args.max_detections

    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    input_w, input_h = imx500.get_input_w_h()
    if np_outputs is None:
        return last_detections
    if args.postprocess == "efficientdet_lite0":
        boxes, scores, classes = \
            postprocess_efficientdet_lite0_detection(outputs=np_outputs, conf_thres=threshold,
                                                     iou_thres=iou, max_out_dets=max_detections)
        from picamera2.devices.imx500.postprocess_yolov5 import scale_boxes
        boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False)

    elif args.postprocess == "yolov5n":
        boxes, scores, classes = \
            postprocess_yolov5_detection(outputs=np_outputs, conf_thres=threshold, iou_thres=iou,
                                         max_out_dets=max_detections)
        from picamera2.devices.imx500.postprocess_yolov5 import scale_boxes
        boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False)

    elif args.postprocess == "yolov8n":
        boxes, scores, classes = \
            postprocess_yolov8_detection(outputs=np_outputs, conf=threshold, iou_thres=iou,
                                         max_out_dets=max_detections)[0]
        boxes = boxes / input_h
    elif args.postprocess == "nanodet":
        boxes, scores, classes = \
            postprocess_nanodet_detection(outputs=np_outputs[0], conf=threshold, iou_thres=iou,
                                          max_out_dets=max_detections)[0]
        from picamera2.devices.imx500.postprocess import scale_boxes
        boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False, False)
    else:
        boxes, scores, classes = np_outputs[0][0], np_outputs[1][0], np_outputs[2][0]
        if bbox_normalization:
            boxes = boxes / input_h

        boxes = np.array_split(boxes, 4, axis=1)
        boxes = zip(*boxes)

    last_detections = [
        Detection(box, category, score, metadata)
        for box, score, category in zip(boxes, scores, classes)
        if score > threshold
    ]
    return last_detections


@lru_cache
def get_labels():
    with open(args.labels, "r") as f:
        labels = f.read().split("\n")

    if args.ignore_dash_labels:
        labels = [l for l in labels if l and l != "-"]
    return labels


def draw_detections(request):
    """Draw the detections for this request onto the ISP output."""
    labels = get_labels()
    with MappedArray(request, "main") as m:
        for detection in last_detections:
            x, y, w, h = detection.box
            label = f"{labels[int(detection.category)]} ({detection.conf:.2f})"
            cv2.putText(m.array, label, (x + 5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            cv2.rectangle(m.array, (x, y), (x + w, y + h), (0, 0, 255, 0))
        if args.preserve_aspect_ratio:
            b = imx500.get_roi_scaled(request)
            cv2.putText(m.array, "ROI", (b.x + 5, b.y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            cv2.rectangle(m.array, (b.x, b.y), (b.x + b.width, b.y + b.height), (255, 0, 0, 0))


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="Path of the model")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--bbox-normalization", action="store_true", help="Normalize bbox")
    parser.add_argument("--threshold", type=float, default=0.55, help="Detection threshold")
    parser.add_argument("--iou", type=float, default=0.65, help="Set iou threshold")
    parser.add_argument("--max-detections", type=int, default=10, help="Set max detections")
    parser.add_argument("--ignore-dash-labels", action="store_true", help="Remove '-' labels ")
    parser.add_argument("--postprocess", choices=["yolov8n", "yolov5n", "nanodet", "efficientdet_lite0"],
                        default=None, help="Run post process of type")
    parser.add_argument("-r", "--preserve-aspect-ratio", action="store_true",
                        help="preprocess the image with  preserve aspect ratio")
    parser.add_argument("--labels", type=str, default="assets/coco_labels.txt",
                        help="Path to the labels file")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()

    # This must be called before instantiation of Picamera2
    imx500 = IMX500(args.model)

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(controls={"FrameRate": args.fps}, buffer_count=28)

    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=True)
    if args.preserve_aspect_ratio:
        imx500.set_auto_aspect_ratio()

    picam2.pre_callback = draw_detections
    queue = queue.Queue()

    def do_parsing(queue):
        global last_detections
        while True:
            metadata_ = queue.get()
            last_detections = parse_detections(metadata_)

    thread = threading.Thread(target=do_parsing, args=(queue,))
    thread.start()

    while True:
        try:
            metadata = picam2.capture_metadata()
            if queue.empty() and "CnnOutputTensor" in metadata:
                queue.put(metadata)
        except KeyError:
            pass
