import os
import time

import cv2
import numpy as np

from picamera2.imx500 import IMX500
from picamera2 import Picamera2

normalSize = (640, 480)
COLOURS = "colours.txt"

last_masks = {}

# This must be called before instantiation of Picamera2
imx500 = IMX500(os.path.abspath("networks/imx500_network_deeplabv3plus.rpk"))
imx500.set_inference_aspect_ratio(imx500.config['input_tensor_size'])

input_tensor_size = (imx500.config['input_tensor']['height'], imx500.config['input_tensor']['width'])

def create_and_draw_masks(request):
    """Create masks from the output tensor and draw them on the main output image."""
    create_masks(request)
    draw_masks(request)


def create_masks(request):
    """Create masks from the output tensor, scaled to the ISP out."""
    labels = None
    global last_masks

    output_tensor = request.get_metadata().get("CnnOutputTensor")
    if output_tensor:
        mask = np.swapaxes(
            np.array(output_tensor).astype(np.uint8).reshape(input_tensor_size),
            0,
            1,
        )
        found_indices = np.unique(mask)
        colours = np.loadtxt(COLOURS)
        for i in found_indices:
            if i == 0:
                continue
            output_shape = [*input_tensor_size, 4]
            colour = [(0, 0, 0, 0), colours[i]]
            overlay = (mask == i).astype(np.uint8)
            overlay = np.array(colour)[overlay].reshape(output_shape).astype(np.uint8)
            overlay = cv2.resize(overlay, normalSize)
            last_masks = {}
            if labels is not None:
                last_masks[labels[i]] = overlay
            else:
                last_masks[i] = overlay
    request.masks = last_masks


def draw_masks(request):
    """Draw the masks for this request onto the ISP output."""
    overlay = np.zeros((normalSize[1], normalSize[0], 4), dtype=np.uint8)
    if request.masks:
        for v in request.masks.values():
            overlay += v
        # Set Alphas and overlay
        overlay[:, :, -1][overlay[:, :, -1] == 255] = 150
        picam2.set_overlay(overlay)


picam2 = Picamera2()
config = picam2.create_preview_configuration(controls={"FrameRate": 30})
picam2.start(config, show_preview=True)

for _ in range(10):
    try:
        t = picam2.capture_metadata()["CnnOutputTensorInfo"]
        output_tensor_info = imx500.get_output_tensor_info(t)
        tensor_data_num = [i['tensor_data_num'] for i in output_tensor_info['info']]
        break
    except KeyError:
        pass

picam2.pre_callback = create_and_draw_masks

while True:
    time.sleep(0.5)
