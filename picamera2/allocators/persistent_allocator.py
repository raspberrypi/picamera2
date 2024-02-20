import logging

from picamera2.allocators import DmaAllocator

_log = logging.getLogger("picamera2")


class PersistentAllocator(DmaAllocator):
    """Persistent DmaHeap Allocator"""

    def __init__(self):
        super().__init__()
        self.buffer_key = None
        self.buffer_dict = {}

    def allocate(self, libcamera_config, use_case):
        if use_case is None:
            _log.error("Must set use_case before using persistent allocator")
        self.buffer_key = use_case

        self.open_fds = []
        self.libcamera_fds = []
        self.frame_buffers = {}
        self.mapped_buffers = {}
        self.mapped_buffers_used = {}

        buffers = self.buffer_dict.get(self.buffer_key)
        if buffers is None:
            super().allocate(libcamera_config, use_case)
            self.buffer_dict[self.buffer_key] = (
                self.open_fds,
                self.libcamera_fds,
                self.frame_buffers,
                self.mapped_buffers,
                self.mapped_buffers_used,
            )
        else:
            (self.open_fds, self.libcamera_fds, self.frame_buffers,
             self.mapped_buffers, self.mapped_buffers_used) = buffers

    def cleanup(self):
        pass

    def deallocate(self, buffer_key=None):
        """Deallocate a set of buffers if no longer in use"""
        if buffer_key is None:
            buffer_key = self.buffer_key

        tmp = super().__new__(DmaAllocator)
        tmp.dmaHeap = None

        (tmp.open_fds, tmp.libcamera_fds, tmp.frame_buffers,
         tmp.mapped_buffers, tmp.mapped_buffers_used) = self.buffer_dict[buffer_key]
        tmp.close()
        del self.buffer_dict[buffer_key]

    def close(self):
        for k in list(self.buffer_dict.keys()):
            self.deallocate(k)
        assert self.buffer_dict == {}
