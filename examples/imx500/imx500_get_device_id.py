#!/usr/bin/python3

from picamera2 import Picamera2
from picamera2.devices.imx500 import IMX500

model = "/usr/share/imx500-models/imx500_network_mobilenet_v2.rpk"

# startup imx500 / picamera2
imx500 = IMX500(model)
picam2 = Picamera2()
config = picam2.create_preview_configuration()
picam2.start(config, show_preview=False)

# wait for the device to be streaming
picam2.capture_metadata()

# get device_id
device_id = imx500.get_device_id()
print("IMX500 Device ID =", device_id)
