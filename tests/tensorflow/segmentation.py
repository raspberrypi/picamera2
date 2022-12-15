#!/usr/bin/python3

# Usage: ./segmentation.py --model deeplapv3.tflite --label deeplab_labels.txt

import argparse
import select
import sys
import time

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
from PIL import Image

from picamera2 import Picamera2, Preview

normalSize = (640, 480)
lowresSize = (320, 240)

masks = {}
captured = []
segmenter = None


def ReadLabelFile(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    ret = {}
    for line in lines:
        pair = line.strip().split(maxsplit=1)
        ret[int(pair[0])] = pair[1].strip()
    return ret


def InferenceTensorFlow(image, model, colours, label=None):
    global masks

    if label:
        labels = ReadLabelFile(label)
    else:
        labels = None

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
    found_indices = np.unique(mask)
    colours = np.loadtxt(colours)
    new_masks = {}
    for i in found_indices:
        if i == 0:
            continue
        output_shape = [o_width, o_height, 4]
        colour = [(0, 0, 0, 0), colours[i]]
        overlay = (mask == i).astype(np.uint8)
        overlay = np.array(colour)[overlay].reshape(output_shape).astype(np.uint8)
        overlay = cv2.resize(overlay, normalSize)
        if labels is not None:
            new_masks[labels[i]] = overlay
        else:
            new_masks[i] = overlay
    masks = new_masks
    print("Found", masks.keys())


def capture_image_and_masks(picam2: Picamera2, model, colour_file, label_file):
    global masks
    # Disable Aec and Awb so all images have the same exposure and colour gains
    picam2.set_controls({"AeEnable": False, "AwbEnable": False})
    time.sleep(1.0)
    request = picam2.capture_request()
    image = request.make_image("main")
    lores = request.make_buffer("lores")
    stride = picam2.stream_configuration("lores")["stride"]
    grey = lores[: stride * lowresSize[1]].reshape((lowresSize[1], stride))

    InferenceTensorFlow(grey, model, colour_file, label_file)
    for k, v in masks.items():
        comp = np.array([0, 0, 0, 0]).reshape(1, 1, 4)
        mask = (~((v == comp).all(axis=-1)) * 255).astype(np.uint8)
        label = k
        label = label.replace(" ", "_")
        if label in captured:
            label = f"{label}{sum(label in x for x in captured)}"
        cv2.imwrite(f"mask_{label}.png", mask)
        image.save(f"img_{label}.png")
        captured.append(label)
    print(masks.keys())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", help="Path of the segmentation model.", required=True
    )
    parser.add_argument("--label", help="Path of the labels file.")
    parser.add_argument("--colours", help="File path of the label colours.")
    parser.add_argument("--output", help="File path of the output image.")
    args = parser.parse_args()

    if args.output:
        output_file = args.output
    else:
        output_file = "out.png"

    if args.label:
        label_file = args.label
    else:
        label_file = None

    if args.colours:
        colour_file = args.colours
    else:
        colour_file = "colours.txt"

    picam2 = Picamera2()
    picam2.start_preview(Preview.QTGL)
    config = picam2.create_preview_configuration(
        main={"size": normalSize}, lores={"size": lowresSize, "format": "YUV420"}
    )
    picam2.configure(config)

    stride = picam2.stream_configuration("lores")["stride"]

    picam2.start()

    try:
        while True:
            buffer = picam2.capture_buffer("lores")
            grey = buffer[: stride * lowresSize[1]].reshape((lowresSize[1], stride))
            InferenceTensorFlow(grey, args.model, colour_file, label_file)
            overlay = np.zeros((normalSize[1], normalSize[0], 4), dtype=np.uint8)
            global masks
            for v in masks.values():
                overlay += v
            # Set Alphas and overlay
            overlay[:, :, -1][overlay[:, :, -1] == 255] = 150
            picam2.set_overlay(overlay)
            # Check if enter has been pressed
            i, o, e = select.select([sys.stdin], [], [], 0.1)
            if i:
                input()
                capture_image_and_masks(picam2, args.model, colour_file, label_file)
                picam2.stop()
                if input("Continue (y/n)?").lower() == "n":
                    raise KeyboardInterrupt
                picam2.start()
    except KeyboardInterrupt:
        print(f"Have captured {captured}")
        todo = input("What to composite?")
        bg = input("Which image to use as background (empty for none)?")
        todo = todo.split()
        images = []
        masks = []
        if bg:
            base_image = Image.open(f"img_{bg}.png")
        else:
            base_image = np.zeros((normalSize[1], normalSize[0], 3), dtype=np.uint8)
            base_image = Image.fromarray(base_image)
        for item in todo:
            images.append(Image.open(f"img_{item}.png"))
            masks.append(Image.open(f"mask_{item}.png"))
        for i in range(len(masks)):
            base_image = Image.composite(images[i], base_image, masks[i])
        base_image.save(output_file)


if __name__ == "__main__":
    main()
