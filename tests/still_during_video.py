#!/usr/bin/python3
from picamera2 import Picamera2
from picamera2.request import CompletedRequest

# Encode a VGA stream, and capture a higher resolution still image half way through.

camera = Picamera2()
half_resolution = [dim // 2 for dim in camera.sensor_resolution]
main_stream = {"size": half_resolution}
lores_stream = {"size": (640, 480)}
video_config = camera.create_video_configuration(main_stream, lores_stream)
camera.configure(video_config)
camera.start()

# It's better to capture the still in this thread, not in the one driving the camera.
request: CompletedRequest = camera.capture_request()
request.make_image("main").convert("RGB").save("test.jpg")
request.release()
print("Still image captured!")

camera.stop()
camera.close()
