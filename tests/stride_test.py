#!/usr/bin/python3

import time

from picamera2 import MappedArray, Picamera2, libcamera


def pre_callback(request):
    # Set the size, to make preview window and MappedArray remapping work
    assert request.config["main"]["stride"] == stride
    request.config["main"]["size"] = full_size
    request.stream_map["main"].configuration.size = libcamera.Size(*full_size)


def post_callback(request):
    # Make right side grey
    with MappedArray(request, "main") as m1:
        a1 = m1.array
        a1[:, -a1.shape[1] // 2:] = 70


picam2 = Picamera2(0)

full_size = (1920, 1080)
half_size = (full_size[0] // 2, full_size[1])
# Calculate stride for full frame
full_config = picam2.create_preview_configuration({"size": full_size})
picam2.configure(full_config)
stride = picam2.camera_config["main"]["stride"]

# Configure as half frame, with full frame stride so right side is blank
picam2.pre_callback = pre_callback
picam2.post_callback = post_callback
main_config = picam2.create_preview_configuration(
    main={"size": half_size, "stride": stride}
)
picam2.configure(main_config)
picam2.start_preview(True)

picam2.start()
time.sleep(2)
