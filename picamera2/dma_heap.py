import ctypes
import fcntl
import logging
import os

from v4l2 import _IOW, _IOWR

_log = logging.getLogger("picamera2")
heapNames = [
    "/dev/dma_heap/vidbuf_cached",
    "/dev/dma_heap/linux,cma"
]


# Kernel stuff from linux/dma-buf.h
class dma_buf_sync(ctypes.Structure):
    _fields_ = [
        ('flags', ctypes.c_uint64),
    ]


DMA_BUF_SYNC_READ = (1 << 0)
DMA_BUF_SYNC_WRITE = (2 << 0)
DMA_BUF_SYNC_RW = (DMA_BUF_SYNC_READ | DMA_BUF_SYNC_WRITE)
DMA_BUF_SYNC_START = (0 << 2)
DMA_BUF_SYNC_END = (1 << 2)

DMA_BUF_BASE = 'b'
DMA_BUF_IOCTL_SYNC = _IOW(DMA_BUF_BASE, 0, dma_buf_sync)

DMA_BUF_SET_NAME = _IOW(DMA_BUF_BASE, 1, ctypes.c_char_p)


# Kernel stuff from linux/dma-heap.h
class dma_heap_allocation_data(ctypes.Structure):
    _fields_ = [
        ('len', ctypes.c_uint64),
        ('fd', ctypes.c_uint32),
        ('fd_flags', ctypes.c_uint32),
        ('heap_flags', ctypes.c_uint64),
    ]


DMA_HEAP_IOC_MAGIC = 'H'

DMA_HEAP_IOCTL_ALLOC = _IOWR(DMA_HEAP_IOC_MAGIC, 0, dma_heap_allocation_data)


# Libcamera C++ classes
class UniqueFD:
    """Libcamera UniqueFD Class"""

    def __init__(self, fd=-1):
        if isinstance(fd, UniqueFD):
            self.__fd = fd.release()
        else:
            self.__fd = fd

    def release(self):
        fd = self.__fd
        self.__fd = -1
        return fd

    def get(self):
        return self.__fd

    def isValid(self):
        return self.__fd >= 0


class DmaHeap:
    """DmaHeap"""

    def __init__(self):
        self.__dmaHeapHandle = UniqueFD()
        for name in heapNames:
            try:
                ret = os.open(name, os.O_CLOEXEC | os.O_RDWR)
            except FileNotFoundError:
                _log.info(f"Failed to open {name}")
                continue

            self.__dmaHeapHandle = UniqueFD(ret)
            break

        if not self.__dmaHeapHandle.isValid():
            raise RuntimeError("Could not open any dmaHeap device")

    @property
    def isValid(self):
        return self.__dmaHeapHandle.isValid()

    def alloc(self, name, size) -> UniqueFD:
        alloc = dma_heap_allocation_data()
        alloc.len = size
        alloc.fd_flags = os.O_CLOEXEC | os.O_RDWR

        ret = fcntl.ioctl(self.__dmaHeapHandle.get(), DMA_HEAP_IOCTL_ALLOC, alloc)
        if ret < 0:
            _log.error(f"dmaHeap allocation failure for {name}")
            return UniqueFD()

        allocFd = UniqueFD(alloc.fd)
        ret = fcntl.ioctl(allocFd.get(), DMA_BUF_SET_NAME, name)
        if not isinstance(ret, bytes) and ret < 0:
            _log.error(f"dmaHeap naming failure for {name}")
            return UniqueFD()

        return allocFd

    def close(self):
        os.close(self.__dmaHeapHandle.get())
