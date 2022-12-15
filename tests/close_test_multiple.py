#!/usr/bin/python3

import multiprocessing
import threading
import time

from picamera2 import Picamera2, Preview


def run_camera(idx):
    camera = Picamera2(idx)
    camera.start_preview(Preview.QT)
    camera.start()
    time.sleep(3)
    camera.stop()
    camera.close()


if __name__ == "__main__":

    if len(Picamera2.global_camera_info()) <= 1:
        print("SKIPPED (one camera)")
        quit()

    multiprocessing.set_start_method("spawn")

    print("Test two processes")
    procs = []
    for i in range(2):
        p = multiprocessing.Process(target=run_camera, args=(i,))
        p.start()
        procs += [p]
    for proc in procs:
        proc.join()

    print("Test camera in main process")
    camera = Picamera2(0)
    camera.start_preview(Preview.QT)
    camera.start()
    time.sleep(3)
    camera.stop()
    camera.close()

    print("Test camera in subprocess")
    p = multiprocessing.Process(target=run_camera, args=(0,))
    p.start()
    p.join()

    print("Test camera in main process and subprocess")
    camera = Picamera2(0)
    camera.start_preview(Preview.QT)
    camera.start()
    p = multiprocessing.Process(target=run_camera, args=(1,))
    p.start()
    p.join()
    camera.stop()
    camera.close()

    print("Test two threads")
    threads = []
    for i in range(2):
        thread = threading.Thread(target=run_camera, args=(i,), daemon=True)
        thread.start()
        threads += [thread]
    for thread in threads:
        thread.join()

    print("Test camera in main process and thread")
    camera = Picamera2(0)
    camera.start_preview(Preview.QT)
    camera.start()
    thread = threading.Thread(target=run_camera, args=(1,), daemon=True)
    thread.start()
    thread.join()
    camera.stop()
    camera.close()
