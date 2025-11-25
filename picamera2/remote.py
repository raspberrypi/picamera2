import mmap
import multiprocessing as mp
import os
import queue
from collections import deque
from concurrent.futures import Future
from ctypes import CDLL, c_int, c_long, get_errno
from threading import Thread
from typing import Any, Callable

import numpy as np
from libcamera import ColorSpace, Transform
from PIL import Image

import picamera2


class Process:
    """
    Creates a new process which receives requests from the parent process.

    A wrapper for multiprocessing.Process that sends requests to a remote process
    and waits for the return values.

    This will timeout if no results are received for the timeout period, even if no requests are sent.

    Args:
        run: The function to run in the child process for each request
        picam2: The Picamera2 object
        init: The function to run in the child process to initialize the process
        timeout: The timeout for the return queue. It has a 1 second resolution.
    """

    def __init__(
            self,
            run: Callable[["RemoteRequest"], Any],
            picam2: picamera2.Picamera2,
            init: Callable[[], None] | None = None,
            timeout: float | None = 30):
        """
        Initializes the Process.

        Some configuration is copied from the Picamera2 object
        """
        self._send_queue = mp.Queue()
        self._return_queue = mp.Queue()

        self._requests_sent = deque()
        self._timeout = timeout
        self._thread = Thread(target=self._return_thread, args=(), daemon=True)
        self._thread.start()

        self._process = _RemoteProcess(self._send_queue, self._return_queue, picam2, run, init)

    def _return_thread(self):
        """Thread that passes the return values to the Future objects."""
        timeout_counter = 0
        while True:
            try:
                result = self._return_queue.get(timeout=1 if self._timeout is not None else None)
            except queue.Empty:
                if not bool(self._requests_sent):
                    timeout_counter = 0
                    continue
                timeout_counter += 1
                if timeout_counter >= self._timeout:
                    _, future = self._requests_sent.popleft()
                    future.set_exception(TimeoutError("No result received for timeout period"))
                continue

            timeout_counter = 0

            if not bool(self._requests_sent):
                break
            request, future = self._requests_sent.popleft()
            future.set_result(result)
            request.release()

    def send(self, request: picamera2.request.CompletedRequest, **kwargs):
        """
        Sends a request to the child process.

        The request is converted to a RemoteRequest object and sent to the child process.
        Returns a Future object that can be used to wait for the result.
        """
        future = Future()
        request.acquire()
        remote = RemoteRequest(request, **kwargs)
        self._send_queue.put(remote)
        self._requests_sent.append((request, future))
        return future

    def close(self):
        """Closes the Process."""
        self._send_queue.put("CLOSE")
        self._thread.join()
        self._process.join()


class _RemoteProcess(mp.Process):
    """
    Starts a new process which receives requests from the parent process.

    The process receives requests from the parent process and runs the given function.
    Then it returns the results back to the parent process.
    """

    def __init__(
            self,
            send_queue: mp.Queue,
            return_queue: mp.Queue,
            picam2: picamera2.Picamera2,
            run: Callable[["RemoteRequest"], Any],
            init: Callable[[], None],
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)
        self._send_queue = send_queue
        self._return_queue = return_queue
        self._return_result = False  # Whether the parent is expecting a result

        self._pid_fd = None
        self._picam2_pid = os.getpid()
        self._array_cache = {}
        self._buffer_cache = {}
        self._request = None
        self._helper = picamera2.request.Helpers(_RemotePicamera2(picam2))

        self._run = run
        self._init_func = init
        self.start()

    def _child_init(self):
        """Initialization that runs in the child process."""
        self._syscall = CDLL(None, use_errno=True).syscall
        self._syscall.argtypes = [c_long]
        if self._init_func is not None:
            self._init_func()

    def run(self):
        """Main loop of the child process."""
        self._child_init()
        while (request := self._capture_request()) is not None:
            value = self._run(request, **request._kwargs)
            self._return_request(value)

    def _map_fd(self, picam2_fd: int):
        """Maps a file descriptor from the parent process to the child process."""
        if self._pid_fd is None:
            self._pid_fd = os.pidfd_open(self._picam2_pid)
        fd = self._syscall(438, c_int(self._pid_fd), c_int(picam2_fd), c_int(0))  # 438 is pidfd_getfd
        if fd == -1:
            errno = get_errno()
            raise OSError(errno, os.strerror(errno))
        return fd

    def _capture_request(self):
        """Captures a request from the parent process."""
        if self._return_result:
            self._return_queue.put(None)
        self._return_result = True

        msg = self._send_queue.get()
        if msg == "CLOSE":
            self._return_queue.put(None)
            return None

        msg._deserialize(self)
        self._request = msg
        return msg

    def _return_request(self, return_value: Any):
        """Returns a request to the parent process."""
        if self._request is None:
            raise ValueError("No request to return")

        if self._request._array_ref_count > 0:
            raise ValueError("Cannot return request while arrays are still in use")

        self._request = None
        self._return_queue.put(return_value)
        self._return_result = False


class RemoteMappedArray:
    """
    A mapped array that is created in the child process.

    Args:
        request: The RemoteRequest object
        stream_name: The name of the stream to map
    """

    def __init__(self, request: "RemoteRequest", stream_name: str):
        """Initializes the RemoteMappedArray."""
        self._request = request
        self._stream_name = stream_name
        self._array = None

    def __enter__(self):
        self._request._array_ref_count += 1
        self._array = self._request._arrays[self._stream_name]
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._request._array_ref_count -= 1
        if self._request._array_ref_count < 0:
            raise ValueError("Array reference count is less than 0")
        self._array = None

    @property
    def array(self):
        """Access the array."""
        return self._array


class RemoteRequest:
    """
    A request that is sent to the child process.

    Args:
        request: The CompletedRequest object
    """

    def __init__(self, request: picamera2.request.CompletedRequest, **kwargs):
        """Initializes and serializes the request."""
        self.request = request
        self._metadata = request.get_metadata()
        self.config = request.config.copy()
        t = self.config["transform"]
        self.config["transform"] = (t.hflip, t.vflip, t.transpose)
        c = self.config["colour_space"]
        self.config["colour_space"] = (c.primaries, c.transferFunction, c.ycbcrEncoding, c.range)
        self._array_ref_count = 0

        self._buffers_fd = {}
        for name in self.request.picam2.stream_map:
            if self.request.picam2.stream_map[name] is None:
                self._buffers_fd[name] = None
            else:
                self._buffers_fd[name] = self._serialize_stream(name)

        self._kwargs = kwargs

        del self.request

    def _serialize_stream(self, stream_name: str):
        """Serializes a stream to a file descriptor and length."""
        plane = self.request.request.buffers[self.request.picam2.stream_map[stream_name]].planes[0]
        fd = plane.fd
        length = plane.length
        return fd, length

    def _deserialize(self, process: _RemoteProcess):
        """Deserializes the request."""
        self._arrays = {}
        self._buffers = {}
        self._process = process
        for name in self._buffers_fd:
            if self._buffers_fd[name] is not None:
                pid_fd, length = self._buffers_fd[name]
                if pid_fd in process._array_cache:
                    self._arrays[name] = process._array_cache[pid_fd]
                    self._buffers[name] = process._buffer_cache[pid_fd]
                else:
                    fd = process._map_fd(pid_fd)
                    buffer = self._deserialize_buffer(fd, length)
                    self._arrays[name] = self._create_array(buffer, name)
                    self._buffers[name] = buffer
                    process._array_cache[pid_fd] = self._arrays[name]
                    process._buffer_cache[pid_fd] = self._buffers[name]

        self.config["transform"] = Transform(
            self.config["transform"][0],
            self.config["transform"][1],
            self.config["transform"][2])
        self.config["colour_space"] = ColorSpace(
            self.config["colour_space"][0],
            self.config["colour_space"][1],
            self.config["colour_space"][2],
            self.config["colour_space"][3])

    def _deserialize_buffer(self, fd: int, length: int):
        """Deserializes a buffer."""
        mem = mmap.mmap(fd, length, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        return mem

    def _create_array(self, mem, name: str):
        """Creates an array from a buffer."""
        array = np.array(mem, copy=False, dtype=np.uint8)
        config = self.config[name]
        width, height = config["size"]
        stride = config["stride"]
        format = config["format"]
        if format == "YUV420":
            return array.reshape((height + height // 2, stride))
        array = array.reshape((height, stride))
        if format in ("RGB888", "BGR888"):
            return array[:, :width * 3].reshape((height, width, 3))
        elif format in ("XBGR8888", "XRGB8888"):
            return array[:, :width * 4].reshape((height, width, 4))
        return array

    def get_metadata(self):
        """Access the metadata."""
        return self._metadata

    def get_config(self):
        """Access the config."""
        return self.config

    def make_buffer(self, stream_name: str):
        """Access the buffer of a stream."""
        return np.array(self._buffers[stream_name], dtype=np.uint8)

    def make_array(self, stream_name: str):
        """Create a numpy array a stream."""
        with RemoteMappedArray(self, stream_name) as m:
            if m.array.data.c_contiguous:
                return np.copy(m.array)
            else:
                return np.ascontiguousarray(m.array)

    def make_image(self, stream_name: str):
        """Create an Image from a stream."""
        config = self.config.get(stream_name, None)
        if config is None:
            raise RuntimeError(f"Stream {stream_name!r} is not defined")

        fmt = config["format"]
        mode = self._process._helper._get_pil_mode(fmt)

        with RemoteMappedArray(self, stream_name) as m:
            shape = m.array.shape
            stride = m.array.strides[0]
            if mode == "RGBX":
                array = np.copy(m.array)
                stride = array.strides[0]
            elif not m.array.data.c_contiguous:
                array = m.array.base
            img = Image.frombuffer("RGB", (shape[1], shape[0]), array, "raw", mode, stride, 1)
        return img

    def save(self, file_output: str, name: str = "main", format_str: str | None = None, exif_data: dict | None = None):
        """Save an image to a file."""
        img = self.make_image(name)
        self._process._helper.save(img, self.get_metadata(), file_output, format_str, exif_data)

    def save_dng(self, file_output: str, name: str = "raw"):
        """Save a the image to a DNG file."""
        buffer = self.make_buffer(name)
        self._process._helper.save_dng(buffer, self.get_metadata(), self.config[name], file_output)


class _FakeObject:
    """A fake object that is used to access the camera properties in the child process."""

    def __init__(self, **kwargs):
        """Initializes the FakeObject."""
        self.__dict__.update(kwargs)


class _RemotePicamera2:
    """
    A fake object that looks like a Picamera2 object in the child process.

    Some of the helper functions get their configuration from the picam2 object.
    This stores the properties that are needed in the child process.
    """

    def __init__(self, picam2: picamera2.Picamera2):
        self.camera = _FakeObject(id=picam2.camera.id)
        self.options = {}
        if "compress_level" in picam2.options:
            self.options["compress_level"] = picam2.options["compress_level"]
        if "quality" in picam2.options:
            self.options["quality"] = picam2.options["quality"]

        self.camera_properties = {}
        if "Model" in picam2.camera_properties:
            self.camera_properties["Model"] = picam2.camera_properties["Model"]


class Pool:
    """
    A pool of processes that are used to process the images.

    This can be used as a context manager to automatically close the pool.

    Args:
        run: The function to run in each child process for each request
        count: The number of processes to create
        picam2: The Picamera2 object
        init: The function to run in each child process to initialize the process
    """

    def __init__(
            self,
            run: Callable[["RemoteRequest"], Any],
            count: int,
            picam2: picamera2.Picamera2,
            init: Callable[[], None] | None = None,
            timeout: float | None = 30):
        """Initializes the Pool."""
        self._processes = [Process(run, picam2, init, timeout) for _ in range(count)]
        self._process_count = count
        self._process_index = 0  # The preferred process for the next request

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def send(self, request: picamera2.request.CompletedRequest, **kwargs):
        """Sends a request to the child process."""
        process = min(
            enumerate(self._processes),
            key=lambda p: (
                len(p[1]._requests_sent),
                (p[0] + self._process_index) % self._process_count
            )
        )[1]
        self._process_index = (self._process_index + 1) % self._process_count

        return process.send(request, **kwargs)

    def close(self):
        """Closes the Pool."""
        for process in self._processes:
            process.close()
