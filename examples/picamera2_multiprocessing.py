#!/usr/bin/python3

# A demonstration of how to pass image buffers to other Python processes, using the
# dmabuf file descriptors so as to avoid copying all the pixel data.

import mmap
import multiprocessing as mp
import os
import queue
from collections import deque
from concurrent.futures import Future
from ctypes import CDLL, c_int, c_long, get_errno
from threading import Thread

import numpy as np


class Process(mp.Process):
    """A separate process for multi-processing that receives shared camera frames from Picamera2."""

    def __init__(self, picam2, name='main', *args, **kwargs):
        """Create a Picamera2 child process. Call after Picamera2 has been configured.

        Arguments:
            picam2 - the Picamera2 object
            name - the name of the stream whose images are to be passed to the child process
        """
        super().__init__(*args, **kwargs)
        self.config = picam2.camera_configuration()[name]
        self._picam2_pid = os.getpid()
        self._pid_fd = None
        self._send_queue = mp.Queue()
        self._return_queue = mp.Queue()
        self._arrays = {}
        self._return_result = False
        self._syscall = CDLL(None, use_errno=True).syscall
        self._syscall.argtypes = [c_long]
        self.start()
        self._stream = picam2.stream_map[name]
        self._requests_sent = deque()
        self._thread = Thread(target=self._return_thread, args=())
        self._thread.start()

    def _return_thread(self):
        # Runs in a thread in the Picamera2 process to return requests to libcamera.
        while True:
            result = self._return_queue.get()  # requests are finished with in the order we sent them
            if not bool(self._requests_sent):
                break  # we get a reply but with no request sent when we're closing down
            request, future = self._requests_sent.popleft()
            future.set_result(result)
            request.release()

    def send(self, request, *args):
        """Call from the Picamera2 process to send an image from this request to the child process.

        Arguments:
            request - the request from which the image is passed to the child process
            args - optional extra parameters that are passed across with the image

        Returns a future which the caller can optionally wait on to get the child process's result.
        """
        plane = request.request.buffers[self._stream].planes[0]
        fd = plane.fd
        length = plane.length
        future = Future()
        request.acquire()
        self._requests_sent.append((request, future))
        self._send_queue.put((fd, length, args))
        return future

    def _format_array(self, mem):
        # Format the memory buffer into a numpy image array.
        array = np.array(mem, copy=False, dtype=np.uint8)
        width, height = self.config['size']
        stride = self.config['stride']
        format = self.config['format']
        if format == 'YUV420':
            return array.reshape((height + height // 2, stride))
        array = array.reshape((height, stride))
        if format in ('RGB888', 'BGR888'):
            return array[:, :width * 3].reshape((height, width, 3))
        elif format in ("XBGR8888", "XRGB8888"):
            return array[:, :width * 4].reshape((height, width, 4))
        return array

    def _map_fd(self, picam2_fd):
        # Map the Picamera2 process's fd to our own. Strictly speaking you don't need this if
        # Picamera2 has already allocated the buffers before it gets forked. But it can be hard
        # to know and there should be no great harm in doing this anyway.
        if self._pid_fd is None:
            self._pid_fd = os.pidfd_open(self._picam2_pid)
        fd = self._syscall(438, c_int(self._pid_fd), c_int(picam2_fd), c_int(0))  # 438 is pidfd_getfd
        if fd == -1:
            errno = get_errno()
            raise OSError(errno, os.strerror(errno))
        return fd

    def capture_shared_array(self):
        """Call from the child process to wait for a shared image array from the Picamera2 process.

        Once the image is received, self.args will contain any parameters that were sent with it.
        Returns the numpy image array, or None if we are being shut down and must quit.
        """
        # Tell the Picamera2 process (if we haven't already) that we're done with the previous image.
        if self._return_result:
            self._return_queue.put(None)
        self._return_result = True
        # Wait for the next image. A "CLOSE" message means they're shutting us down.
        msg = self._send_queue.get()
        if msg == "CLOSE":
            self._return_queue.put(None)
            return None
        # We have a new buffer. The message contains Picamera2's fd, the buffer length and arguments.
        picam2_fd, length, self.args = msg
        if picam2_fd in self._arrays:  # have we seen this buffer before?
            return self._arrays[picam2_fd]
        # Otherwise create a local fd, and mmap it to create a numpy image array.
        fd = self._map_fd(picam2_fd)
        mem = mmap.mmap(fd, length, mmap.MAP_SHARED, mmap.PROT_READ)
        array = self._format_array(mem)
        self._arrays[picam2_fd] = array
        return array

    def set_result(self, result):
        """Call from the child process to return a result to the Picamera2 process.

        In turn, this will cause the Picamera2 process to release the request back to libcamera.
        Calling this is optional; if you don't, the next call to capture_shared_array will dispose
        of the image anyway.
        """
        self._return_result = False
        self._return_queue.put(result)

    def run(self):
        """Derived classes should override this to define what the child process does."""
        pass

    def close(self):
        """Call from the Picamera2 process to close the child process."""
        self._send_queue.put("CLOSE")
        self._thread.join()
        self.join()
        super().close()


# The multi-processing module has a Pool class, though I can't see how to make it run my
# own derived Process instances. Maybe I've missed something. Anyhow, here follows a
# simple-minded implementation thereof.

class Pool:
    """A pool of Picamera2 child processes to which tasks can be sent."""

    def __init__(self, num_processes, process, picam2, name='main', maxsize=0, *args, **kwargs):
        """Create a Picamera2 child process pool."""
        self._processes = [process(picam2, name, *args, **kwargs) for _ in range(num_processes)]
        self._futures = queue.Queue(maxsize=maxsize)
        self._count = 0
        for p in self._processes:
            p._count = 0
        self._thread = Thread(target=self._handle_thread, args=())
        self._thread.start()

    def send(self, request, *args):
        """Call from the Picamera2 process to send an image to one of the pool's child processes.

        Arguments: as per Process.send.
        Returns nothing. The child process's return value will be passed to handle_result.
        """
        # Choose the process with least pending work to do, and the LRU among those.
        process = min(self._processes, key=lambda p: (len(p._requests_sent), p._count))
        self._count += 1
        process._count = self._count
        self._futures.put(process.send(request, *args))

    def _handle_thread(self):
        # Thread in the Picamera2 process to wait for and handle child process results.
        while True:
            future = self._futures.get()
            if future is None:  # happens when we're being closed
                break
            self.handle_result(future.result())

    def handle_result(self, result):
        """Derived classes should override this to define what to do with the child process results."""
        pass

    def close(self):
        """Call from the Picamera2 process to close the pool and all the child processes."""
        for p in self._processes:
            p.close()
        self._futures.put(None)
        self._thread.join()


# Below here is all demo/test code.

if __name__ == "__main__":
    # Simple test showing how to use the Process class.
    from picamera2 import Picamera2

    class MyProcess(Process):
        def run(self):
            while (array := self.capture_shared_array()) is not None:
                print(array.shape, self.args)
                self.set_result(self.args[0])  # send back the parameter we were given!

    picam2 = Picamera2()
    config = picam2.create_preview_configuration({'format': 'RGB888'})
    picam2.start(config)

    process = MyProcess(picam2, 'main')  # send images from the "main" stream to the child process

    for _ in range(50):
        with picam2.captured_request() as request:
            exposure_time = request.get_metadata()['ExposureTime']
            future = process.send(request, exposure_time)
            if exposure_time != future.result():
                print("ERROR: exposure time has come back different!")

    process.close()

    # Here's a similar thing using a Pool, which starts 4 other processes.
    import time

    class MyProcess2(Process):
        def run(self):
            while self.capture_shared_array() is not None:
                print("Received:", self.args[0])
                time.sleep(0.05)
                self.set_result(self.args[0])  # after a delay, return the parameter we were given

    class MyPool(Pool):
        def handle_result(self, result):
            print("Finished:", result)

    pool = MyPool(num_processes=4, process=MyProcess2, picam2=picam2, name='main', maxsize=10)

    for i in range(50):
        with picam2.captured_request() as request:
            pool.send(request, i)

    pool.close()
