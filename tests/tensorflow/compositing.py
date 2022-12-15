#!/usr/bin/python3

# Usage: ./compositing.py --model mobilenet_v2.tflite --label coco_labels.txt

import argparse
from picamera2 import Picamera2, Preview, MappedArray
import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
from PIL import Image
import time
import select
import sys


normalSize = (640, 480)
lowresSize = (320, 240)

rectangles = []
captured = []


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
            if len(rect) == 5:
                text = rect[4]
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(
                    m.array,
                    text,
                    (int(rect[0] * 2) + 10, int(rect[1] * 2) + 10),
                    font,
                    1,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )


def InferenceTensorFlow(image, model, label=None):
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
            box = [xmin, ymin, xmax, ymax]
            rectangles.append(box)
            if labels:
                print(labels[classId], "score = ", score)
                rectangles[-1].append(labels[classId])
            else:
                print("score = ", score)


def capture_image_and_masks(picam2: Picamera2, model, label_file):
    global rectangles
    picam2.post_callback = None
    # Disable Aec and Awb so all images have the same exposure and colour gains
    picam2.set_controls({"AeEnable": False, "AwbEnable": False})
    time.sleep(0.2)
    request = picam2.capture_request()
    image = request.make_image("main")
    lores = request.make_buffer("lores")
    stride = picam2.stream_configuration("lores")["stride"]
    grey = lores[: stride * lowresSize[1]].reshape((lowresSize[1], stride))
    InferenceTensorFlow(grey, model, label_file)
    for rect in rectangles:
        print(image.size)
        mask = np.zeros((image.size[1], image.size[0]), dtype=np.uint8)
        rect_start = (int(rect[0] * 2), int(rect[1] * 2))
        rect_end = (int(rect[2] * 2), int(rect[3] * 2))
        cv2.rectangle(mask, rect_start, rect_end, color=(255,), thickness=-1)
        label = rect[4]
        label = label.replace(" ", "_")
        if label in captured:
            label = f"{label}{sum(label in x for x in captured)}"
        cv2.imwrite(f"mask_{label}.png", mask)
        image.save(f"img_{label}.png")
        captured.append(label)
    print(rectangles)
    picam2.post_callback = DrawRectangles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Path of the detection model.", required=True)
    parser.add_argument("--label", help="Path of the labels file.")
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

    picam2 = Picamera2()
    picam2.start_preview(Preview.QTGL)
    config = picam2.create_preview_configuration(
        main={"size": normalSize}, lores={"size": lowresSize, "format": "YUV420"}
    )
    picam2.configure(config)

    stride = picam2.stream_configuration("lores")["stride"]
    picam2.post_callback = DrawRectangles

    picam2.start()

    try:
        print("Starting capture, press enter to capture objects")
        while True:
            buffer = picam2.capture_buffer("lores")
            grey = buffer[: stride * lowresSize[1]].reshape((lowresSize[1], stride))
            InferenceTensorFlow(grey, args.model, label_file)
            # Check if enter has been pressed
            i, o, e = select.select([sys.stdin], [], [], 0.1)
            if i:
                input()
                capture_image_and_masks(picam2, args.model, label_file)
                if input("Continue (y/n)?").lower() == "n":
                    raise KeyboardInterrupt
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
