import fcntl
import logging
import mmap
import os

import libcamera

from picamera2.allocators.allocator import Allocator, Sync
from picamera2.dma_heap import (DMA_BUF_IOCTL_SYNC, DMA_BUF_SYNC_END,
                                DMA_BUF_SYNC_READ, DMA_BUF_SYNC_RW,
                                DMA_BUF_SYNC_START, DmaHeap, dma_buf_sync)

_log = logging.getLogger("picamera2")


class DmaAllocator(Allocator):
    """DmaHeap Allocator"""

    def __init__(self):
        super().__init__()
        self.dmaHeap = DmaHeap()
        self.mapped_buffers = {}
        self.mapped_buffers_used = {}
        self.frame_buffers = {}
        self.open_fds = []
        self.libcamera_fds = []
        self.sync = self.DmaSync

    def allocate(self, libcamera_config, _):
        # Delete old buffers
        self.libcamera_fds = []
        self.cleanup()
        # Close our copies of fds
        for fd in self.open_fds:
            os.close(fd)
        self.frame_buffers = {}
        self.open_fds = []

        for c, stream_config in enumerate(libcamera_config):
            stream = stream_config.stream
            fb = []
            for i in range(stream_config.buffer_count):
                fd = self.dmaHeap.alloc(f"picamera2-{i}", stream_config.frame_size)
                # Keep track of our allocated fds, as libcamera makes copies
                self.open_fds.append(fd.get())

                if not fd.isValid():
                    raise RuntimeError(f"failed to allocate capture buffers for stream {c}")

                plane = [libcamera.FrameBuffer.Plane()]
                plane[0].fd = fd.get()
                plane[0].offset = 0
                plane[0].length = stream_config.frame_size

                self.libcamera_fds.append(plane[0].fd)
                self.mapped_buffers_used[plane[0].fd] = False

                fb.append(libcamera.FrameBuffer(plane))
                memory = mmap.mmap(plane[0].fd, stream_config.frame_size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
                self.mapped_buffers[fb[-1]] = memory

            self.frame_buffers[stream] = fb
            msg = f"Allocated {len(fb)} buffers for stream {c} with fds {[f.planes[0].fd for f in self.frame_buffers[stream]]}"
            _log.debug(msg)

    def buffers(self, stream):
        return self.frame_buffers[stream]

    def acquire(self, buffers):
        for buffer in buffers.values():
            fd = buffer.planes[0].fd
            self.mapped_buffers_used[fd] = True

    def release(self, buffers):
        for buffer in buffers.values():
            fd = buffer.planes[0].fd
            self.mapped_buffers_used[fd] = False
        self.cleanup()

    def cleanup(self):
        for k, v in self.mapped_buffers.items():
            fd = k.planes[0].fd
            if not self.mapped_buffers_used[fd] and fd not in self.libcamera_fds:
                # Not in use by any requests, and not currently allocated
                v.close()
                del self.mapped_buffers_used[fd]
        for k in [k for k, v in self.mapped_buffers.items() if v.closed]:
            del self.mapped_buffers[k]

    def close(self):
        self.libcamera_fds = []
        self.cleanup()
        # Close our copies of fds
        for fd in self.open_fds:
            os.close(fd)
        self.frame_buffers = {}
        self.open_fds = []
        if self.dmaHeap is not None:
            self.dmaHeap.close()

    def __del__(self):
        self.close()

    class DmaSync(Sync):
        """Dma Buffer Sync"""

        def __init__(self, allocator, fb, write):
            self.allocator = allocator
            self.__fb = fb
            self.__write = write

        def __enter__(self):
            dma_sync = dma_buf_sync()
            dma_sync.flags = DMA_BUF_SYNC_START | (DMA_BUF_SYNC_RW if self.__write else DMA_BUF_SYNC_READ)

            it = self.allocator.mapped_buffers.get(self.__fb, None)
            if it is None:
                raise RuntimeError("failed to find buffer in DmaSync")

            ret = fcntl.ioctl(self.__fb.planes[0].fd, DMA_BUF_IOCTL_SYNC, dma_sync)
            if ret:
                raise RuntimeError("failed to lock-sync-write dma buf")
            return it

        def __exit__(self, exc_type=None, exc_value=None, exc_traceback=None):
            dma_sync = dma_buf_sync()
            dma_sync.flags = DMA_BUF_SYNC_END | (DMA_BUF_SYNC_RW if self.__write else DMA_BUF_SYNC_READ)

            ret = fcntl.ioctl(self.__fb.planes[0].fd, DMA_BUF_IOCTL_SYNC, dma_sync)
            if ret:
                logging.error("failed to unlock-sync-write dma buf")
