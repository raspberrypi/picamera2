class Allocator:
    """Base class for allocators"""

    def __init__(self):
        self.sync = Sync

    def allocate(self, libcamera_config, use_case):
        pass

    def buffers(self, stream):
        pass

    def acquire(self, bufs):
        pass

    def release(self, bufs):
        pass

    def close(self):
        pass


class Sync:
    """Base class for allocator syncronisations"""

    def __init__(self, allocator, fb, write):
        self.__fb = fb

    def __enter__(self):
        import mmap

        # Check if the buffer is contiguous and find the total length.
        fd = self.__fb.planes[0].fd
        planes_metadata = self.__fb.metadata.planes
        buflen = 0
        for p, p_metadata in zip(self.__fb.planes, planes_metadata):
            # bytes_used is the same as p.length for regular frames, but correctly reflects
            # the compressed image size for MJPEG cameras.
            buflen = buflen + p_metadata.bytes_used
            if fd != p.fd:
                raise RuntimeError('_MappedBuffer: Cannot map non-contiguous buffer!')

        self.__mm = mmap.mmap(fd, buflen, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        return self.__mm

    def __exit__(self, exc_type=None, exc_value=None, exc_traceback=None):
        if self.__mm is not None:
            self.__mm.close()
