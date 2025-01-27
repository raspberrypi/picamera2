#!/usr/bin/env python3

"""Example module for Hailo Detection."""

import argparse

import cv2

from picamera2 import MappedArray, Picamera2, Preview
from picamera2.devices import Hailo


def extract_detections(hailo_output, w, h, class_names, threshold=0.5):
    """Extract detections from the HailoRT-postprocess output."""
    results = []
    for class_id, detections in enumerate(hailo_output):
        for detection in detections:
            score = detection[4]
            if score >= threshold:
                y0, x0, y1, x1 = detection[:4]
                bbox = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
                results.append([class_names[class_id], bbox, score])
    return results


def draw_objects(request):
    current_detections = detections
    if current_detections:
        with MappedArray(request, "main") as m:
            for class_name, bbox, score in current_detections:
                x0, y0, x1, y1 = bbox
                label = f"{class_name} %{int(score * 100)}"
                cv2.rectangle(m.array, (x0, y0), (x1, y1), (0, 255, 0, 0), 2)
                cv2.putText(m.array, label, (x0 + 5, y0 + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0, 0), 1, cv2.LINE_AA)


if __name__ == "__main__":
    # Parse command-line arguments.
    parser = argparse.ArgumentParser(description="Detection Example")
    parser.add_argument("-m", "--model", help="Path for the HEF model.",
                        default="/usr/share/hailo-models/yolov8s_h8l.hef")
    parser.add_argument("-l", "--labels", default="coco.txt",
                        help="Path to a text file containing labels.")
    parser.add_argument("-s", "--score_thresh", type=float, default=0.5,
                        help="Score threshold, must be a float between 0 and 1.")
    args = parser.parse_args()

    # Get the Hailo model, the input size it wants, and the size of our preview stream.
    with Hailo(args.model) as hailo:
        model_h, model_w, _ = hailo.get_input_shape()
        video_w, video_h = 1280, 960

        # Load class names from the labels file
        with open(args.labels, 'r', encoding="utf-8") as f:
            class_names = f.read().splitlines()

        # The list of detected objects to draw.
        detections = None

        # Configure and start Picamera2.
        with Picamera2() as picam2:
            main = {'size': (video_w, video_h), 'format': 'XRGB8888'}
            lores = {'size': (model_w, model_h), 'format': 'RGB888'}
            controls = {'FrameRate': 30}
            config = picam2.create_preview_configuration(main, lores=lores, controls=controls)
            picam2.configure(config)

            picam2.start_preview(Preview.QTGL, x=0, y=0, width=video_w, height=video_h)
            picam2.start()
            picam2.pre_callback = draw_objects

            # Process each low resolution camera frame.
            while True:
                frame = picam2.capture_array('lores')

                # Run inference on the preprocessed frame
                results = hailo.run(frame)

                # Extract detections from the inference results
                detections = extract_detections(results, video_w, video_h, class_names, args.score_thresh)
