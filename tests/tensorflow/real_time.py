#!/usr/bin/python3

# Copyright (c) 2022 Raspberry Pi Ltd
# Author: Alasdair Allan <alasdair@raspberrypi.com>
# SPDX-License-Identifier: BSD-3-Clause

# A TensorFlow Lite example for Picamera2 on Raspberry Pi OS Bullseye
#
# Install necessary dependences before starting,
#
# $ sudo apt update
# $ sudo apt install build-essential
# $ sudo apt install libatlas-base-dev
# $ sudo apt install python3-pip
# $ pip3 install tflite-runtime
# $ pip3 install opencv-python==4.4.0.46
# $ pip3 install pillow
# $ pip3 install numpy
#
# and run from the command line,
#
# $ python3 real_time.py --model mobilenet_v2.tflite --label coco_labels.txt

import argparse
import os
import sys

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
from PIL import Image, ImageDraw, ImageFont

from picamera2 import MappedArray, Picamera2, Preview

normalSize = (640, 480)
lowresSize = (320, 240)

rectangles = []


def ReadLabelFile(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    ret = {}
    for line in lines:
        pair = line.strip().split(maxsplit=1)
        ret[int(pair[0])] = pair[1].strip()
    return ret


def DrawRectangles(request):
    with MappedArray(request, "main") as m:
        for rect in rectangles:
            rect_start = (int(rect[0] * 2) - 5, int(rect[1] * 2) - 5)
            rect_end = (int(rect[2] * 2) + 5, int(rect[3] * 2) + 5)
            cv2.rectangle(m.array, rect_start, rect_end, (0, 255, 0, 0))


def InferenceTensorFlow(image, model, output, label=None):
    global rectangles

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
    floating_model = False
    if input_details[0]["dtype"] == np.float32:
        floating_model = True

    rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    initial_h, initial_w, channels = rgb.shape

    picture = cv2.resize(rgb, (width, height))

    input_data = np.expand_dims(picture, axis=0)
    if floating_model:
        input_data = (np.float32(input_data) - 127.5) / 127.5

    interpreter.set_tensor(input_details[0]["index"], input_data)

    interpreter.invoke()

    detected_boxes = interpreter.get_tensor(output_details[0]["index"])
    detected_classes = interpreter.get_tensor(output_details[1]["index"])
    detected_scores = interpreter.get_tensor(output_details[2]["index"])
    num_boxes = interpreter.get_tensor(output_details[3]["index"])

    rectangles = []
    for i in range(int(num_boxes)):
        top, left, bottom, right = detected_boxes[0][i]
        classId = int(detected_classes[0][i])
        score = detected_scores[0][i]
        if score > 0.5:
            xmin = left * initial_w
            ymin = bottom * initial_h
            xmax = right * initial_w
            ymax = top * initial_h
            if labels:
                print(labels[classId], "score = ", score)
            else:
                print("score = ", score)
            box = [xmin, ymin, xmax, ymax]
            rectangles.append(box)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Path of the detection model.", required=True)
    parser.add_argument("--label", help="Path of the labels file.")
    parser.add_argument("--output", help="File path of the output image.")
    args = parser.parse_args()

    if args.output:
        output_file = args.output
    else:
        output_file = "out.jpg"

    if args.label:
        label_file = args.label
    else:
        label_file = None

    picam2 = Picamera2()
    picam2.start_preview(Preview.QTGL)
    config = picam2.create_preview_configuration(
        main={"size": normalSize}, lores={"size": lowresSize, "format": "YUV420"}
    )
    picam2.configure(config)

    stride = picam2.stream_configuration("lores")["stride"]
    picam2.post_callback = DrawRectangles

    picam2.start()

    while True:
        buffer = picam2.capture_buffer("lores")
        grey = buffer[: stride * lowresSize[1]].reshape((lowresSize[1], stride))
        result = InferenceTensorFlow(grey, args.model, output_file, label_file)


if __name__ == "__main__":
    main()
