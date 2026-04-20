#!/bin/python3

import os

from picamera2 import Picamera2
from picamera2.devices.imx500 import IMX500

# Check if an imx500 camera is connected.
camera_info = Picamera2.global_camera_info()
camera_num = next((c['Num'] for c in camera_info if c['Model'] == 'imx500'), None)

if camera_num is None:
    print("SKIPPED (no imx500 camera found)")
    quit()

model_path = '/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk'
if not os.path.exists(model_path):
    print("SKIPPED (model file not found:", model_path + ")")
    quit()

imx500 = IMX500(model_path)

# Start the camera and capture some frames with output tensors.
picam2 = Picamera2(imx500.camera_num)
config = picam2.create_preview_configuration(buffer_count=12)
picam2.configure(config)
picam2.start()

# wait for the device to be streaming before reading id.
picam2.capture_metadata()
device_id = imx500.get_device_id()
print("Device ID:", device_id)
if not device_id:
    print("ERROR: empty device ID")
    picam2.stop()
    picam2.close()
    exit()

NUM_FRAMES = 30

tensor_count = 0
for _ in range(NUM_FRAMES):
    metadata = picam2.capture_metadata()
    outputs = imx500.get_outputs(metadata, add_batch=True)
    if outputs is not None and len(outputs) > 0:
        tensor_count += 1

print("Got output tensors on", tensor_count, "of", NUM_FRAMES, "frames")
if tensor_count < NUM_FRAMES // 2:
    print("ERROR: expected at least", NUM_FRAMES // 2, "frames with output tensors, got", tensor_count)

picam2.stop()
picam2.close()
