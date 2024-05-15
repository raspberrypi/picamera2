import os
import struct

import cv2
import numpy as np

import picamera2.sony_ivs as IVS
from picamera2 import Picamera2

normalSize = (640, 480)
COLOURS = "colours.txt"

last_masks = {}


def create_and_draw_masks(request):
    """Create masks from the output tensor and draw them on the main output image."""
    create_masks(request)
    draw_masks(request)


def create_masks(request):
    """Create masks from the output tensor, scaled to the ISP out."""
    labels = None
    global last_masks

    output_tensor = request.get_metadata().get("Imx500OutputTensor")
    if output_tensor:
        mask = np.swapaxes(
            np.array(output_tensor).astype(np.uint8).reshape(INPUT_TENSOR_SIZE),
            0,
            1,
        )
        found_indices = np.unique(mask)
        colours = np.loadtxt(COLOURS)
        for i in found_indices:
            if i == 0:
                continue
            output_shape = [*INPUT_TENSOR_SIZE, 4]
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


def input_tensor_image(input_tensor, input_tensor_size):
    """Convert input tensor in planar format to interleaved RGB."""
    r1 = (
        np.array(input_tensor, dtype=np.uint8)
        .view(np.int8)
        .reshape((3,) + input_tensor_size)
    )
    r2 = r1[(2, 1, 0), :, :]
    return (np.transpose(r2, (1, 2, 0)) + 128).clip(0, 255).astype(np.uint8)


# This must be called before instantiation of Picamera2
IVS.set_network_firmware(os.path.abspath("networks/imx500_network_deeplabv3plus.fpk"))

picam2 = Picamera2()
config = picam2.create_preview_configuration(controls={"FrameRate": 30})
picam2.start(config, show_preview=True)

for _ in range(10):
    try:
        input_tensor_info = picam2.capture_metadata()["Imx500InputTensorInfo"]
        network_name, width, height, num_channels = struct.unpack(
            "64sIII", bytes(input_tensor_info)
        )
        network_name = network_name.decode("utf-8").rstrip("\x00")
        break
    except KeyError:
        pass

for _ in range(10):
    try:
        output_tensor_info = picam2.capture_metadata()["Imx500OutputTensorInfo"]
        network_name, *tensor_data_num, num_tensors = struct.unpack(
            "64s16II", bytes(output_tensor_info)
        )
        network_name = network_name.decode("utf-8").rstrip("\x00")
        tensor_data_num = tensor_data_num[:num_tensors]
        break
    except KeyError:
        pass

INPUT_TENSOR_SIZE = (height, width)

picam2.pre_callback = create_and_draw_masks

cv2.startWindowThread()
while True:
    try:
        input_tensor = picam2.capture_metadata()["Imx500InputTensor"]
        if INPUT_TENSOR_SIZE != (0, 0):
            cv2.imshow(
                "Input Tensor",
                IVS.input_tensor_image(
                    input_tensor, INPUT_TENSOR_SIZE, (384, 384, 384), (0, 0, 0)
                ),
            )
            cv2.resizeWindow("Input Tensor", *INPUT_TENSOR_SIZE)
    except KeyError:
        pass
