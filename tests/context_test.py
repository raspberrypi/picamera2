import time

from picamera2 import Picamera2


def main():
    print("With context...")
    time.sleep(1)
    with Picamera2() as picam2:
        preview = picam2.create_preview_configuration()
        picam2.configure(preview)
        picam2.start()
        metadata = picam2.capture_metadata("context_test.jpg")
        print(metadata)
    time.sleep(5)
    print("Without context...")
    time.sleep(1)
    picam2 = Picamera2()
    preview = picam2.create_preview_configuration()
    picam2.configure(preview)
    picam2.start()
    metadata = picam2.capture_metadata("no_context_test.jpg")
    print(metadata)
    picam2.stop_preview()
    picam2.close()


if __name__ == "__main__":
    main()
