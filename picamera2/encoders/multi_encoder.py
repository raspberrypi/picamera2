from concurrent.futures import ThreadPoolExecutor
import queue
import threading

from picamera2.encoders.encoder import Encoder


class MultiEncoder(Encoder):
    """This is a base class for a multi-threaded software encoder. Derive your encoder
    from this class and add an encode_func method. For an example, see JpegEncoder
    (jpeg_encoder.py). The parallelism is likely to help when the encoder in question
    releases the GIL, for example before diving into a large C/C++ library.
    Parameters:
    num_threads - the number of parallel threads to use. Probably match this to the
                  number of cores available for best performance.
    """
    def __init__(self, num_threads=4):
        super().__init__()
        self.threads = ThreadPoolExecutor(num_threads)
        self.tasks = queue.Queue()

    def _start(self):
        super()._start()
        self.thread = threading.Thread(target=self.output_thread, daemon=True)
        self.thread.start()

    def _stop(self):
        super()._stop()
        self.tasks.put(None)
        self.thread.join()

    def output_thread(self):
        while True:
            task = self.tasks.get()
            if task is None:
                return

            buffer = task.result()
            if self.output:
                self.output.outputframe(buffer)

    def do_encode(self, request):
        buffer = self.encode_func(request, request.picam2.encode_stream_name)
        request.release()
        return buffer

    def encode(self, stream, request):
        if self._running:
            request.acquire()
            self.tasks.put(self.threads.submit(self.do_encode, request))
