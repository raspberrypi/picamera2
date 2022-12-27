import time

from picamera2 import Picamera2


def main():
    print("With context...")
    time.sleep(1)
    with Picamera2() as camera:
        preview = camera.create_preview_configuration()
        camera.configure(preview)
        camera.start()
        metadata = camera.capture_metadata()
        print(metadata)
    time.sleep(5)
    print("Without context...")
    time.sleep(1)
    camera = Picamera2()
    preview = camera.create_preview_configuration()
    camera.configure(preview)
    camera.start()
    metadata = camera.capture_metadata()
    print(metadata)
    camera.stop_preview()
    camera.close()


if __name__ == "__main__":
    main()
