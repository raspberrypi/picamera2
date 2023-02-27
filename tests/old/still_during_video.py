#!/usr/bin/python3
from scicamera import Camera, CameraConfig
from scicamera.request import CompletedRequest

# Encode a VGA stream, and capture a higher resolution still image half way through.

camera = Camera()
half_resolution = tuple(dim // 2 for dim in camera.sensor_resolution)
video_config = CameraConfig.for_video(
    camera, main={"size": half_resolution}, lores={"size": half_resolution}
)
camera.configure(video_config)
camera.start()

# It's better to capture the still in this thread, not in the one driving the camera.
request: CompletedRequest = camera.capture_request().result()
request.make_image("main").convert("RGB").save("test.jpg")
request.release()
print("Still image captured!")

camera.stop()
camera.close()
