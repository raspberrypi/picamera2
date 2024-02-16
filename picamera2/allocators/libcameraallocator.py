import logging

import libcamera

from picamera2.allocators.allocator import Allocator

_log = logging.getLogger("picamera2")


class LibcameraAllocator(Allocator):
    """Uses the libcamera FrameBufferAllocator"""

    def __init__(self, camera):
        super().__init__()
        self.camera = camera

    def allocate(self, libcamera_config, _):
        self.allocator = libcamera.FrameBufferAllocator(self.camera)
        streams = [stream_config.stream for stream_config in libcamera_config]
        for i, stream in enumerate(streams):
            if self.allocator.allocate(stream) < 0:
                logging.critical("Failed to allocate buffers.")
                raise RuntimeError("Failed to allocate buffers.")
            msg = f"Allocated {len(self.allocator.buffers(stream))} buffers for stream {i}"
            _log.debug(msg)

    def buffers(self, stream):
        return self.allocator.buffers(stream)
