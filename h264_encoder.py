import picamera2
import selectors
import threading
import queue
import atexit
import fcntl
import mmap
import select
import time
from encoder import *
from v4l2 import *

class H264Encoder(Encoder):

    def __init__(self, bitrate):
        super().__init__()
        self.bufs = {}
        self._bitrate = bitrate

    def _start(self):
        super()._start()
        self.vd = open('/dev/video11', 'rb+', buffering=0)

        self.buf_available = queue.Queue()
        self.buf_frame = queue.Queue()

        self.thread = threading.Thread(target=self.thread_poll, args=(self.buf_available,))
        self.thread.setDaemon(True)
        self.thread.start()

        cp = v4l2_capability()
        fcntl.ioctl(self.vd, VIDIOC_QUERYCAP, cp)

        ctrl = v4l2_control()
        ctrl.id = V4L2_CID_MPEG_VIDEO_BITRATE
        ctrl.value = self._bitrate
        fcntl.ioctl(self.vd, VIDIOC_S_CTRL, ctrl)

        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
        fmt.fmt.pix_mp.width = self._width
        fmt.fmt.pix_mp.height = self._height
        fmt.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_YUV420
        fmt.fmt.pix_mp.plane_fmt[0].bytesperline = self.width # is this correct?
        fmt.fmt.pix_mp.field = V4L2_FIELD_ANY
        fmt.fmt.pix_mp.colorspace = V4L2_COLORSPACE_JPEG
        fmt.fmt.pix_mp.num_planes = 1
        fcntl.ioctl(self.vd, VIDIOC_S_FMT, fmt)

        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
        fmt.fmt.pix_mp.width = self._width
        fmt.fmt.pix_mp.height = self._height
        fmt.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_H264
        fmt.fmt.pix_mp.field = V4L2_FIELD_ANY
        fmt.fmt.pix_mp.colorspace = V4L2_COLORSPACE_DEFAULT
        fmt.fmt.pix_mp.num_planes = 1
        fmt.fmt.pix_mp.plane_fmt[0].bytesperline = 0
        fmt.fmt.pix_mp.plane_fmt[0].sizeimage = 512 << 10
        fcntl.ioctl(self.vd, VIDIOC_S_FMT, fmt)

        NUM_OUTPUT_BUFFERS = 6
        NUM_CAPTURE_BUFFERS = 12

        reqbufs = v4l2_requestbuffers()
        reqbufs.count = NUM_OUTPUT_BUFFERS
        reqbufs.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
        reqbufs.memory = V4L2_MEMORY_DMABUF
        fcntl.ioctl(self.vd, VIDIOC_REQBUFS, reqbufs)

        for i in range(reqbufs.count):
            self.buf_available.put(i)

        reqbufs = v4l2_requestbuffers()
        reqbufs.count = NUM_CAPTURE_BUFFERS
        reqbufs.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
        reqbufs.memory = V4L2_MEMORY_MMAP
        fcntl.ioctl(self.vd, VIDIOC_REQBUFS, reqbufs)

        for i in range(reqbufs.count):
            planes = v4l2_plane * VIDEO_MAX_PLANES
            planes = planes()
            buffer = v4l2_buffer()
            ctypes.memset(ctypes.byref(buffer), 0, ctypes.sizeof(buffer))
            buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
            buffer.memory = V4L2_MEMORY_MMAP
            buffer.index = i
            buffer.length = 1
            buffer.m.planes = planes
            ret = fcntl.ioctl(self.vd, VIDIOC_QUERYBUF, buffer)
            self.bufs[i] = ( mmap.mmap(self.vd.fileno(), buffer.m.planes[0].length, mmap.PROT_READ | mmap.PROT_WRITE, mmap.MAP_SHARED,
                               offset=buffer.m.planes[0].m.mem_offset) , buffer.m.planes[0].length)
            ret = fcntl.ioctl(self.vd, VIDIOC_QBUF, buffer)

        typev = v4l2_buf_type(V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE)
        fcntl.ioctl(self.vd, VIDIOC_STREAMON, typev)
        typev = v4l2_buf_type(V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE)
        fcntl.ioctl(self.vd, VIDIOC_STREAMON, typev)

    def _stop(self):
        super()._stop()
        self.thread.join()
        typev = v4l2_buf_type(V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE)
        fcntl.ioctl(self.vd, VIDIOC_STREAMOFF, typev)
        typev = v4l2_buf_type(V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE)
        fcntl.ioctl(self.vd, VIDIOC_STREAMOFF, typev)

        reqbufs = v4l2_requestbuffers()
        reqbufs.count = 0
        reqbufs.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
        reqbufs.memory = V4L2_MEMORY_DMABUF
        fcntl.ioctl(self.vd, VIDIOC_REQBUFS, reqbufs)

        for i in range(len(self.bufs)):
            self.bufs[i][0].close()
        self.bufs = {}

        reqbufs = v4l2_requestbuffers()
        reqbufs.count = 0
        reqbufs.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
        reqbufs.memory = V4L2_MEMORY_MMAP
        fcntl.ioctl(self.vd, VIDIOC_REQBUFS, reqbufs)
        self.vd.close()

    def thread_poll(self, buf_available):
        pollit = select.poll()
        pollit.register(self.vd, select.POLLIN)

        while self._running:
            for fd, event in pollit.poll(200):
                if event & select.POLLIN:
                    buf = v4l2_buffer()
                    planes = v4l2_plane * VIDEO_MAX_PLANES
                    planes = planes()
                    buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
                    buf.memory = V4L2_MEMORY_DMABUF
                    buf.length = 1
                    buf.m.planes = planes
                    ret = fcntl.ioctl(self.vd, VIDIOC_DQBUF, buf)

                    if ret == 0:
                        buf_available.put(buf.index)

                    buf = v4l2_buffer()
                    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
                    buf.memory = V4L2_MEMORY_MMAP
                    buf.length = 1
                    ctypes.memset(planes, 0, ctypes.sizeof(v4l2_plane) * VIDEO_MAX_PLANES)
                    buf.m.planes = planes
                    ret = fcntl.ioctl(self.vd, VIDIOC_DQBUF, buf)

                    if ret == 0:
                        bufindex = buf.index
                        buflen = buf.m.planes[0].length

                        # Write output to file
                        b = self.bufs[buf.index][0].read(buf.m.planes[0].bytesused)
                        self.bufs[buf.index][0].seek(0)
                        if self._output is not None:
                            self._output.write(b)

                        # Requeue encoded buffer
                        buf = v4l2_buffer()
                        planes = v4l2_plane * VIDEO_MAX_PLANES
                        planes = planes()
                        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
                        buf.memory = V4L2_MEMORY_MMAP
                        buf.index = bufindex
                        buf.length = 1
                        buf.m.planes = planes
                        buf.m.planes[0].bytesused = 0
                        buf.m.planes[0].length = buflen
                        ret = fcntl.ioctl(self.vd, VIDIOC_QBUF, buf)

                        # Release frame from camera
                        l = self.buf_frame.get()
                        l.release()

    def encode(self, stream, request):
        cfg = stream.configuration
        width, height = cfg.size
        fb = request.request.buffers[stream]
        fd = fb.fd(0)
        stride = cfg.stride
        request.acquire()

        buf = v4l2_buffer()
        timestamp_us = fb.metadata.timestamp / 1000

        # Pass frame to video 4 linux, to encode
        planes = v4l2_plane * VIDEO_MAX_PLANES
        planes = planes()
        buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
        buf.index = self.buf_available.get()
        buf.field = V4L2_FIELD_NONE
        buf.memory = V4L2_MEMORY_DMABUF
        buf.length = 1
        buf.timestamp.tv_sec = timestamp_us / 1000000
        buf.timestamp.tv_usec = timestamp_us % 1000000
        buf.m.planes = planes
        buf.m.planes[0].m.fd = fd
        buf.m.planes[0].bytesused = cfg.frameSize
        buf.m.planes[0].length = cfg.frameSize
        ret = fcntl.ioctl(self.vd, VIDIOC_QBUF, buf)
        self.buf_frame.put(request)
