#!/usr/bin/python3

import time
from threading import Lock

from picamera2 import MappedArray, Picamera2, libcamera

cam2_request = None
lock = Lock()


def pre_callback(request):
    # Set the size, to make preview window and MappedArray remapping work
    request.config["main"]["size"] = full_size
    request.stream_map["main"].configuration.size = libcamera.Size(*full_size)


def copy_image(request):
    global cam2_request
    with lock:
        request_2 = cam2_request
        if request_2 is None:
            return
        request_2.acquire()
    # Copy second image into right hand side of main image
    with MappedArray(request, "main") as m1, MappedArray(request_2, "main") as m2:
        a1 = m1.array
        a2 = m2.array
        a1[:, -a2.shape[1]:] = a2
    request_2.release()


def save_request(request):
    # Store most recent request for use by other camera
    global cam2_request
    with lock:
        if cam2_request is not None:
            cam2_request.release()
        request.acquire()
        cam2_request = request


picam2a = Picamera2(0)

full_size = (1920, 1080)
half_size = (full_size[0] // 2, full_size[1])
# Calculate stride for full frame
full_config = picam2a.create_preview_configuration({"size": full_size})
picam2a.configure(full_config)
stride = picam2a.camera_config["main"]["stride"]

# Configure as half frame, with full frame stride so right side is blank
picam2a.pre_callback = pre_callback
picam2a.post_callback = copy_image
main_config = picam2a.create_preview_configuration(
    main={"size": half_size, "stride": stride},
    controls={"ScalerCrop": (0, 0, picam2a.sensor_resolution[0], picam2a.sensor_resolution[1])}
)
picam2a.configure(main_config)
picam2a.start_preview(True)

# Configure as half frame normally
picam2b = Picamera2(1)
picam2b.pre_callback = save_request
half_config = picam2a.create_preview_configuration(
    main={"size": half_size},
    controls={"ScalerCrop": (0, 0, picam2a.sensor_resolution[0], picam2a.sensor_resolution[1])}
)
picam2b.configure(half_config)

picam2a.start()
picam2b.start()
time.sleep(10)
