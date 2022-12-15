#!/usr/bin/python3

# A small OCR demo. To install pytesseract:
# sudo apt install -y tesseract-ocr libtesseract-dev
# pip3 install pytesseract

from pprint import pprint

import cv2
import pytesseract

from picamera2 import MappedArray, Picamera2, Preview

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration({"size": (1024, 768)}))
picam2.start_preview(Preview.QTGL)
picam2.start()

threshold = 50

display_data = []


def output_text(request):
    colour = (0, 255, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX
    with MappedArray(request, "main") as m:
        for item in display_data:
            x, y, w, h = item["box"]
            cv2.putText(
                m.array,
                item["text"],
                (x, y),
                font,
                (h + 4) / 35,
                colour,
                (h + 12) // 12,
            )


picam2.post_callback = output_text

while True:
    array = picam2.capture_array()
    data = [line.split("\t") for line in pytesseract.image_to_data(array).split("\n")][
        1:-1
    ]
    data = [
        {
            "text": item[11],
            "conf": int(item[10]),
            "box": (item[6], item[7], item[8], item[9]),
        }
        for item in data
    ]
    data = [
        item for item in data if item["conf"] > threshold and not item["text"].isspace()
    ]
    for item in data:
        item["box"] = tuple(map(int, item["box"]))
    pprint(data, width=500, sort_dicts=False)
    display_data = data
