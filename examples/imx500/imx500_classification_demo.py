import argparse
import os
import struct

import cv2
import numpy as np

from picamera2.imx500 import IMX500
from picamera2 import MappedArray, Picamera2

with open("labels.txt", "r") as f:
    LABELS = f.read().split("\n")

parser = argparse.ArgumentParser()
parser.add_argument("--model", type=str, required=True, help="Path of the model")

args = parser.parse_args()

MODEL = args.model

last_results = []


class Classification:
    def __init__(self, id, score):
        """Create a Classification object, recording the id and score."""
        self.id = id
        self.score = score


def parse_and_draw_classification_results(request):
    """Analyse the classification results in the output tensor and draw them on the main output image."""
    parse_classification_results(request)
    draw_classification_results(request)


def parse_classification_results(request, stream="main"):
    """Parse the output tensor into a top 3 classification results."""
    output_tensor = request.get_metadata().get("CnnOutputTensor")
    if output_tensor:
        results = np.array(output_tensor)
        top_indices = np.argpartition(-results, 3)[:3]
        global last_results
        last_results = [Classification(index, results[index]) for index in top_indices]
    request.results = last_results


def draw_classification_results(request, stream="main"):
    """Draw the classification results for this request onto the ISP output."""
    with MappedArray(request, stream) as m:
        for index, result in enumerate(request.results):
            if LABELS is not None:
                if OUTPUT_TENSOR_SIZE == 1000:
                    label = LABELS[result.id + 1]
                else:
                    label = LABELS[result.id]
            else:
                label = result.id
            text = f"{label}: {result.score}"
            cv2.putText(
                m.array,
                text,
                (5, 15 + index * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )


# This must be called before instantiation of Picamera2
imx500 = IMX500.from_network_file(os.path.abspath(MODEL))

picam2 = Picamera2()
config = picam2.create_preview_configuration(controls={"FrameRate": 30, "CnnEnableInputTensor": True})
picam2.start(config, show_preview=True)

for _ in range(10):
    try:
        t = picam2.capture_metadata()["CnnInputTensorInfo"]
        network_name, width, height, num_channels = imx500.get_input_tensor_info(t)
        break
    except KeyError:
        pass

for _ in range(10):
    try:
        t = picam2.capture_metadata()["CnnOutputTensorInfo"]
        output_tensor_info = imx500.get_output_tensor_info(t)
        tensor_data_num = [i['tensor_data_num'] for i in output_tensor_info['info']]
        break
    except KeyError:
        pass

INPUT_TENSOR_SIZE = (height, width)
OUTPUT_TENSOR_SIZE = tensor_data_num[0]

# Will not be needed once the input tensor is embedded in the network rpk
imx500.config['input_tensor_size'] = (width, height)
imx500.set_inference_aspect_ratio(imx500.config['input_tensor_size'], picam2.sensor_resolution)

picam2.pre_callback = parse_and_draw_classification_results

cv2.startWindowThread()
while True:
    try:
        input_tensor = picam2.capture_metadata()["CnnInputTensor"]
        if input_tensor is None:
            print("Input tensor missing")
        if INPUT_TENSOR_SIZE != (0, 0):
            cv2.imshow(
                "Input Tensor",
                imx500.input_tensor_image(input_tensor)
            )
            cv2.resizeWindow("Input Tensor", *INPUT_TENSOR_SIZE)
    except KeyError:
        pass
