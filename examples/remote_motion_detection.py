#!/usr/bin/python3

# This shows how to use the remote module to detect motion in an image.
# The captured frames are sent to a child process.
# The motion is estimated in the child process and returned to the main process where it is drawn on the image.

import queue
import threading

import cv2
import numpy as np

import picamera2
from picamera2 import MappedArray, Process, RemoteMappedArray

BLOCK_SIZE = 32
SEARCH_SIZE = 16
STEP_SIZE = 8

last_frame = None
motion_map = None


def run(request):
    global last_frame

    if last_frame is None:
        last_frame = request.make_array("main")
        return None

    with RemoteMappedArray(request, "main") as m:
        motion_map = calculate_motion(last_frame, m.array)

    last_frame = request.make_array("main")

    return motion_map


def return_thread(futures):
    global motion_map

    while True:
        future = futures.get()
        motion_map = future.result()


def calculate_motion(frame1, frame2):
    motion_map = np.zeros((frame1.shape[0] // BLOCK_SIZE, frame1.shape[1] // BLOCK_SIZE, 2), dtype=np.int8)
    for block_x in range(0, frame1.shape[1], BLOCK_SIZE):
        for block_y in range(0, frame1.shape[0], BLOCK_SIZE):
            block = frame1[block_y:block_y + BLOCK_SIZE, block_x:block_x + BLOCK_SIZE]
            min_diff = np.inf
            max_diff = 0
            for offset_x in range(-SEARCH_SIZE, SEARCH_SIZE + 1, STEP_SIZE):
                if block_x + offset_x < 0 or block_x + offset_x + BLOCK_SIZE >= frame2.shape[1]:
                    continue
                for offset_y in range(-SEARCH_SIZE, SEARCH_SIZE + 1, STEP_SIZE):
                    if block_y + offset_y < 0 or block_y + offset_y + BLOCK_SIZE >= frame2.shape[0]:
                        continue
                    block2 = frame2[block_y + offset_y:block_y + offset_y + BLOCK_SIZE,
                                    block_x + offset_x:block_x + offset_x + BLOCK_SIZE]
                    diff = np.sum((block - block2)**2)
                    if diff < min_diff:
                        min_diff = diff
                        min_offset = (offset_x, offset_y)
                    if diff > max_diff:
                        max_diff = diff

            if max_diff < 4 * min_diff:
                motion_map[block_y // BLOCK_SIZE, block_x // BLOCK_SIZE] = (0, 0)
            else:
                motion_map[block_y // BLOCK_SIZE, block_x // BLOCK_SIZE] = min_offset

    return motion_map


def draw_motion_map(request):
    if motion_map is None:
        return

    with MappedArray(request, "main") as m:
        for block_x in range(0, motion_map.shape[1]):
            for block_y in range(0, motion_map.shape[0]):
                mid_x = block_x * BLOCK_SIZE + BLOCK_SIZE // 2
                mid_y = block_y * BLOCK_SIZE + BLOCK_SIZE // 2
                offset_x, offset_y = motion_map[block_y, block_x]
                cv2.arrowedLine(m.array, (mid_x, mid_y), (mid_x + offset_x, mid_y + offset_y), (0, 0, 255), 2)


if __name__ == "__main__":
    picam2 = picamera2.Picamera2()
    config = picam2.create_preview_configuration(buffer_count=2)
    picam2.configure(config)
    picam2.post_callback = draw_motion_map
    picam2.start_preview(picamera2.Preview.QTGL)
    picam2.start()

    process = Process(run, picam2)

    futures = queue.Queue()
    return_thread = threading.Thread(target=return_thread, args=(futures,))
    return_thread.start()

    for _ in range(1000):
        with picam2.captured_request() as request:
            future = process.send(request)
            futures.put(future)

    return_thread.join()
