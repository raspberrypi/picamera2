"""This is a base class for a multi-threaded software encoder."""

import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from picamera2.encoders.encoder import Encoder


class MultiEncoder(Encoder):
    """This is a base class for a multi-threaded software encoder.

    Derive your encoder from this class and add an encode_func method. For an example, see JpegEncoder
    (jpeg_encoder.py). The parallelism is likely to help when the encoder in question
    releases the GIL, for example before diving into a large C/C++ library.
    Parameters:
    num_threads - the number of parallel threads to use. Probably match this to the number of cores available for
    best performance.
    """

    def __init__(self, num_threads: int = 4) -> None:
        """Initialise mult-threaded encoder

        :param num_threads: Number of threads to use, defaults to 4
        :type num_threads: int, optional
        """
        super().__init__()
        self.threads = ThreadPoolExecutor(num_threads)
        self.tasks = queue.Queue()

    def _start(self) -> None:
        self.thread = threading.Thread(target=self.output_thread, daemon=True)
        self.thread.start()

    def _stop(self) -> None:
        self.tasks.put(None)
        self.thread.join()

    def output_thread(self) -> None:
        """Outputs frame"""
        while True:
            task = self.tasks.get()
            if task is None:
                return

            buffer, timestamp_us = task.result()
            if self.output:
                self.outputframe(buffer, timestamp=timestamp_us)

    def do_encode(self, request, stream) -> tuple[bytes, int]:
        """Encodes frame in a thread

        :param request: Request
        :return: Buffer
        """
        fb = request.request.buffers[stream]
        timestamp_us = self._timestamp(fb)
        buffer = self.encode_func(request, request.picam2.encode_stream_name)
        request.release()
        return (buffer, timestamp_us)

    def _encode(self, stream, request) -> None:
        """Encode frame using a thread

        :param stream: Stream
        :param request: Request
        """
        if self._running:
            request.acquire()
            self.tasks.put(self.threads.submit(self.do_encode, request, stream))

    def encode_func(self, request, name) -> bytes:
        """Empty function, which will be overriden"""
        return b""
