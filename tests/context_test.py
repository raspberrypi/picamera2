import time

from picamera2 import Picamera2


def main():
    print("With context...")
    with Picamera2() as camera:
        preview = camera.create_preview_configuration()
        camera.configure(preview)
        camera.start()
        metadata = camera.capture_metadata().result()
        assert isinstance(metadata, dict)
        print(metadata)

    print("Without context...")
    camera = Picamera2()
    preview = camera.create_preview_configuration()
    camera.configure(preview)
    camera.start()
    metadata = camera.capture_metadata().result()
    print(metadata)
    camera.stop_preview()
    camera.close()


if __name__ == "__main__":
    main()
