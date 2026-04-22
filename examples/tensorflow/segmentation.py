#!/usr/bin/python3

# Usage: ./segmentation.py --model deeplabv3.tflite --label deeplab_labels.txt

import argparse
import select
import sys
import time

import cv2
import numpy as np
from ai_edge_litert.interpreter import Interpreter
from PIL import Image

from picamera2 import Picamera2, Platform

NORMAL_SIZE = (640, 480)


def read_label_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    ret = {}
    for line in lines:
        pair = line.strip().split(maxsplit=1)
        ret[int(pair[0])] = pair[1].strip()
    return ret


class Model:
    def __init__(self, model_path, label_file, colour_file):
        self.interpreter = Interpreter(model_path=model_path, num_threads=4)
        self.interpreter.allocate_tensors()

        input_details = self.interpreter.get_input_details()
        output_details = self.interpreter.get_output_details()
        self.height = input_details[0]['shape'][1]
        self.width = input_details[0]['shape'][2]
        self.o_height = output_details[0]['shape'][1]
        self.o_width = output_details[0]['shape'][2]
        self.floating_model = input_details[0]['dtype'] == np.float32
        self.input_index = input_details[0]['index']
        self.output_index = output_details[0]['index']

        self.labels = read_label_file(label_file) if label_file else None
        self.colours = np.loadtxt(colour_file)

    def run_inference(self, image):
        """Ensure image is RGB, run segmentation, return masks dict."""
        if len(image.shape) == 2:
            # Image is YUV420. Must convert and trim off any padding.
            image = cv2.cvtColor(image, cv2.COLOR_YUV420p2RGB)
        image = image[: self.height, : self.width]
        input_data = np.expand_dims(image, axis=0)
        if self.floating_model:
            input_data = np.float32(input_data / 255)

        self.interpreter.set_tensor(self.input_index, input_data)
        self.interpreter.invoke()
        output = self.interpreter.get_tensor(self.output_index)[0]

        seg_mask = np.argmax(output, axis=-1)
        found_indices = np.unique(seg_mask)
        masks = {}
        for i in found_indices:
            if i == 0:
                continue
            output_shape = [self.o_width, self.o_height, 4]
            colour = [(0, 0, 0, 0), self.colours[i]]
            overlay = (seg_mask == i).astype(np.uint8)
            overlay = np.array(colour)[overlay].reshape(output_shape).astype(np.uint8)
            overlay = cv2.resize(overlay, NORMAL_SIZE)
            key = self.labels[i] if self.labels is not None else i
            masks[key] = overlay
        print("Found", list(masks.keys()))
        return masks


def capture_image_and_masks(picam2: Picamera2, model: Model, captured: list):
    # Disable Aec and Awb so all images have the same exposure and colour gains
    picam2.set_controls({"AeEnable": False, "AwbEnable": False})
    time.sleep(1.0)
    with picam2.captured_request() as request:
        image = request.make_array("main")
        lores = request.make_array("lores")

    masks = model.run_inference(lores)
    for k, v in masks.items():
        mask = (v[..., 3] != 0).astype(np.uint8) * 255
        label = str(k).replace(" ", "_")
        if label in captured:
            label = f"{label}{sum(label in x for x in captured)}"
        cv2.imwrite(f"mask_{label}.png", mask)
        cv2.imwrite(f"img_{label}.png", image)
        captured.append(label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', help='Path of the segmentation model.', required=True)
    parser.add_argument('--label', help='Path of the labels file.')
    parser.add_argument('--colours', help='File path of the label colours.')
    parser.add_argument('--output', help='File path of the output image.')
    args = parser.parse_args()

    output_file = args.output if args.output else 'out.png'
    label_file = args.label
    colour_file = args.colours if args.colours else "colours.txt"

    model = Model(args.model, label_file, colour_file)
    lowres_format = 'YUV420'
    if Picamera2.platform == Platform.PISP:
        # Could try setting the format to BGR888 or RGB888 here which would save a colour conversion
        pass
    LOWRES_SIZE = ((model.width + 1) & ~1, (model.height + 1) & ~1)
    captured = []

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": NORMAL_SIZE}, lores={"size": LOWRES_SIZE, "format": lowres_format}
    )
    picam2.configure(config)

    picam2.start(show_preview=True)

    try:
        while True:
            image = picam2.capture_array("lores")
            masks = model.run_inference(image)
            overlay = np.zeros((NORMAL_SIZE[1], NORMAL_SIZE[0], 4), dtype=np.uint8)
            for v in masks.values():
                overlay += v
            # Set Alphas and overlay
            overlay[:, :, -1][overlay[:, :, -1] == 255] = 150
            picam2.set_overlay(overlay)
            # Check if enter has been pressed
            i, _, _ = select.select([sys.stdin], [], [], 0.1)
            if i:
                input()
                capture_image_and_masks(picam2, model, captured)
                picam2.stop()
                if input("Continue (y/n)?").lower() == "n":
                    raise KeyboardInterrupt
                picam2.start()
    except KeyboardInterrupt:
        print(f"Have captured {captured}")
        todo = input("What to composite?")
        bg = input("Which image to use as background (empty for none)?")
        if bg:
            base_image = Image.open(f"img_{bg}.png")
        else:
            base_image = np.zeros((NORMAL_SIZE[1], NORMAL_SIZE[0], 3), dtype=np.uint8)
            base_image = Image.fromarray(base_image)
        for item in todo.split():
            image = Image.open(f"img_{item}.png")
            mask = Image.open(f"mask_{item}.png")
            base_image = Image.composite(image, base_image, mask)
        base_image.save(output_file)


if __name__ == '__main__':
    main()
