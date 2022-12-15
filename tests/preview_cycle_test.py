import time

from picamera2 import Picamera2, Preview

wait = 5
buffer = 1


def main():
    # First we create a camera instance.
    picam2 = Picamera2()

    # Let's set it up for previewing.
    preview = picam2.create_preview_configuration()
    picam2.configure(preview)

    picam2.start(show_preview=None)

    qtgl1 = time.monotonic()
    print("QT GL Preview")
    time.sleep(buffer)
    picam2.start_preview(Preview.QTGL)
    time.sleep(wait)
    picam2.stop_preview()
    qtgl2 = time.monotonic()

    null1 = time.monotonic()
    print("Null Preview")
    time.sleep(buffer)
    picam2.start_preview(Preview.NULL)
    time.sleep(wait)
    picam2.stop_preview()
    null2 = time.monotonic()

    qt1 = time.monotonic()
    print("QT Preview")
    time.sleep(buffer)
    picam2.start_preview(Preview.QT)
    time.sleep(wait)
    picam2.stop_preview()
    qt2 = time.monotonic()

    # drm1 = time.monotonic()
    # print("DRM Preview")
    # time.sleep(1)
    # picam2.start_preview('drm',x=100,y=100)
    # time.sleep(10)
    # picam2.stop_preview()
    # drm2 = time.monotonic()

    # Close the camera.
    picam2.close()

    print(f"QT GL Cycle Results: {qtgl2-qtgl1-wait-buffer} s")
    print(f"Null Cycle Results: {null2-null1-wait-buffer} s")
    print(f"QT Cycle Results: {qt2-qt1-wait-buffer} s")


if __name__ == "__main__":
    Picamera2.set_logging()
    main()
