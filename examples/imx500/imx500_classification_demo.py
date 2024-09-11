import time
from typing import List
import argparse
import cv2
import numpy as np
from picamera2.devices import IMX500
from picamera2 import MappedArray, Picamera2, CompletedRequest
from picamera2.devices.imx500.postprocess import softmax

last_detections = []
LABELS = None


class Classification:
    def __init__(self, idx: int, score: float):
        """Create a Classification object, recording the idx and score."""
        self.idx = idx
        self.score = score


def get_label(request: CompletedRequest, idx: int) -> str:
    """Retrieve the label corresponding to the classification index."""
    global LABELS
    if LABELS is None:
        with open(args.labels, "r") as f:
            LABELS = f.read().splitlines()
        assert len(LABELS) in [1000, 1001], "Labels file should contain 1000 or 1001 labels."
        output_tensor_size = imx500.get_output_shapes(request.get_metadata())[0][0]
        if output_tensor_size == 1000:
            LABELS = LABELS[1:]  # Ignore the background label if present
    return LABELS[idx]


def parse_and_draw_classification_results(request: CompletedRequest):
    """Analyse and draw the classification results in the output tensor."""
    results = parse_classification_results(request)
    draw_classification_results(request, results)


def parse_classification_results(request: CompletedRequest) -> List[Classification]:
    """Parse the output tensor into the classification results above the threshold."""
    global last_detections
    np_outputs = imx500.get_outputs(request.get_metadata())
    if np_outputs is None:
        return last_detections
    np_output = np_outputs[0]
    if args.softmax:
        np_output = softmax(np_output)
    top_indices = np.argpartition(-np_output, 3)[:3]  # Get top 3 indices with the highest scores
    top_indices = top_indices[np.argsort(-np_output[top_indices])]  # Sort the top 3 indices by their scores
    last_detections = [Classification(index, np_output[index]) for index in top_indices]
    return last_detections


def draw_classification_results(request: CompletedRequest, results: List[Classification], stream: str = "main"):
    """Draw the classification results for this request onto the ISP output."""
    with MappedArray(request, stream) as m:
        if args.preserve_aspect_ratio:
            # drawing roi box
            b = imx500.get_roi_scaled(request)
            cv2.putText(m.array, "ROI", (b.x + 5, b.y + 15), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 0, 0), 1)
            cv2.rectangle(m.array, (b.x, b.y), (b.x + b.width, b.y + b.height), (255, 0, 0, 0))
            text_left, text_top = b.x, b.y + 20
        else:
            text_left, text_top = 0, 0
        # drawing labels (in the ROI box if exist)
        for index, result in enumerate(results):
            label = get_label(request, idx=result.idx)
            text = f"{label}: {result.score:.3f}"
            cv2.putText(m.array, text, (text_left + 5, text_top + 15 + index * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)


def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="Path of the model")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("-s", "--softmax", action="store_true", help="Add post-process softmax")
    parser.add_argument("-r", "--preserve-aspect-ratio", action="store_true",
                        help="preprocess the image with preserve aspect ratio")
    parser.add_argument("--labels", type=str, default="assets/imagenet_labels.txt",
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
    # Register the callback to parse and draw classification results
    picam2.pre_callback = parse_and_draw_classification_results

    while True:
        time.sleep(0.5)
