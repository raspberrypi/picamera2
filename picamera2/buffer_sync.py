import ctypes
import fcntl
import logging
import os

from .dma_heap import *

_log = logging.getLogger("picamera2")


class BufferSync:
    def __init__(self, picam2, fb, write):
        self.picam2 = picam2
        self.__fb = fb
        self.__write = write

    def __enter__(self):
        dma_sync = dma_buf_sync()
        dma_sync.flags = DMA_BUF_SYNC_START | (DMA_BUF_SYNC_RW if self.__write else DMA_BUF_SYNC_READ)

        it = self.picam2.mapped_buffers.get(self.__fb, None)
        if it is None:
            _log.error("failed to find buffer in BufferWriteSync")
            return

        ret = fcntl.ioctl(self.__fb.planes[0].fd, DMA_BUF_IOCTL_SYNC, dma_sync)
        if ret:
            _log.error("failed to lock-sync-write dma buf")
            return

        self.__planes = it

    def __exit__(self, exc_type, exc_value, exc_traceback):
        dma_sync = dma_buf_sync()
        dma_sync.flags = DMA_BUF_SYNC_END | (DMA_BUF_SYNC_RW if self.__write else DMA_BUF_SYNC_READ)

        ret = fcntl.ioctl(self.__fb.planes[0].fd, DMA_BUF_IOCTL_SYNC, dma_sync)
        if ret:
            _log.error("failed to unlock-sync-write dma buf")

    def get(self):
        return self.__planes
