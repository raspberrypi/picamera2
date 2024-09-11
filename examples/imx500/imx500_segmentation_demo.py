import argparse
import time
from typing import Dict
import cv2
import numpy as np
from picamera2.devices import IMX500
from picamera2 import Picamera2, CompletedRequest


COLOURS = np.loadtxt("assets/colours.txt")
WINDOW_SIZE = (640, 480)


def create_and_draw_masks(request: CompletedRequest):
    """Create masks from the output tensor and draw them on the main output image."""
    masks = create_masks(request)
    draw_masks(masks)


def create_masks(request: CompletedRequest) -> Dict[int, np.ndarray]:
    """Create masks from the output tensor, scaled to the ISP out."""
    res = {}
    np_outputs = imx500.get_outputs(metadata=request.get_metadata())
    input_w, input_h = imx500.get_input_w_h()
    if np_outputs is None:
        return res
    mask = np_outputs[0]
    found_indices = np.unique(mask)

    for i in found_indices:
        if i == 0:
            continue
        output_shape = [input_h, input_w, 4]
        colour = [(0, 0, 0, 0), COLOURS[int(i)]]
        overlay = np.array(mask == i, dtype=np.uint8)
        overlay = np.array(colour)[overlay].reshape(output_shape).astype(np.uint8)
        overlay = cv2.resize(overlay, WINDOW_SIZE)
        res[i] = overlay
    return res


def draw_masks(masks: Dict[int, np.ndarray]):
    """Draw the masks for this request onto the ISP output."""
    if not masks:
        return
    overlay = np.zeros((WINDOW_SIZE[1], WINDOW_SIZE[0], 4), dtype=np.uint8)
    if masks:
        for v in masks.values():
            overlay += v
        # Set Alphas and overlay
        overlay[:, :, -1][overlay[:, :, -1] == 255] = 150
        picam2.set_overlay(overlay)


def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="Path of the model")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()

    # This must be called before instantiation of Picamera2
    imx500 = IMX500(args.model)

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(controls={'FrameRate': args.fps}, buffer_count=28)
    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=True)
    picam2.pre_callback = create_and_draw_masks

    while True:
        time.sleep(0.5)
