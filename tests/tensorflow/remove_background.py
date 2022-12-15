#!/usr/bin/python3

# Usage: ./remove_background.py --model deeplapv3.tflite --background thing.png

import argparse

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
from PIL import Image

from picamera2 import Picamera2, Preview

normalSize = (640, 480)
lowresSize = (320, 240)

background_mask = None
background_img = None


def InferenceTensorFlow(image, model):
    global background_mask

    interpreter = tflite.Interpreter(model_path=model, num_threads=4)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    height = input_details[0]["shape"][1]
    width = input_details[0]["shape"][2]
    o_height = output_details[0]["shape"][1]
    o_width = output_details[0]["shape"][2]
    floating_model = False
    if input_details[0]["dtype"] == np.float32:
        floating_model = True

    rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

    picture = cv2.resize(rgb, (width, height))

    input_data = np.expand_dims(picture, axis=0)
    if floating_model:
        input_data = np.float32(input_data / 255)

    interpreter.set_tensor(input_details[0]["index"], input_data)

    interpreter.invoke()

    output = interpreter.get_tensor(output_details[0]["index"])[0]

    mask = np.argmax(output, axis=-1)
    output_shape = (o_width, o_height)
    overlay = (mask == 0).astype(np.uint8)
    overlay = np.array([0, 255])[overlay].reshape(output_shape).astype(np.uint8)
    overlay = cv2.resize(overlay, normalSize)
    background_mask = Image.fromarray(overlay)


def main():
    global background_img
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", help="Path of the segmentation model.", required=True
    )
    parser.add_argument("--background", help="Path of the background image.")
    args = parser.parse_args()

    picam2 = Picamera2()
    picam2.start_preview(Preview.QTGL)
    config = picam2.create_preview_configuration(
        main={"size": normalSize}, lores={"size": lowresSize, "format": "YUV420"}
    )
    picam2.configure(config)

    stride = picam2.stream_configuration("lores")["stride"]

    picam2.start()

    if args.background:
        background_img = Image.open(args.background)
        background_img = background_img.resize(normalSize)
    else:
        background_img = np.zeros((normalSize[1], normalSize[0], 3), dtype=np.uint8)
        background_img = Image.fromarray(background_img)

    while True:
        buffer = picam2.capture_buffer("lores")
        grey = buffer[: stride * lowresSize[1]].reshape((lowresSize[1], stride))
        InferenceTensorFlow(grey, args.model)
        base_img = np.zeros((normalSize[1], normalSize[0], 3), dtype=np.uint8)
        base_img = Image.fromarray(base_img)
        global background_mask
        overlay = Image.composite(background_img, base_img, background_mask)
        overlay.putalpha(background_mask)
        overlay = np.array(overlay)
        picam2.set_overlay(overlay)


if __name__ == "__main__":
    main()
