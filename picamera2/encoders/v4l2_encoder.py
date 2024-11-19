"""Provide V4L2 encoding functionality"""

import ctypes
import fcntl
import mmap
import queue
import select
import threading

from v4l2 import *

from picamera2.encoders.encoder import Encoder


class V4L2Encoder(Encoder):
    """V4L2 Encoding"""

    def __init__(self, bitrate, pixformat):
        """Initialise V4L2 encoder

        :param bitrate: Bitrate
        :type bitrate: int
        :param pixformat: Pixel format
        :type pixformat: int
        """
        super().__init__()
        self.bufs = {}
        # The encoder's _setup method will calculate the final bitrate.
        self.bitrate = bitrate
        self._pixformat = pixformat
        self._controls = []
        self.vd = None
        self.framerate = None
        self._enable_framerate = False

    @property
    def _v4l2_format(self):
        """The input format to the codec, as a V4L2 type."""
        FORMAT_TABLE = {"RGB888": V4L2_PIX_FMT_BGR24,
                        "BGR888": V4L2_PIX_FMT_RGB24,
                        "XBGR8888": V4L2_PIX_FMT_BGR32,
                        "XRGB8888": V4L2_PIX_FMT_RGBA32,
                        "YUV420": V4L2_PIX_FMT_YUV420}
        if self._format not in FORMAT_TABLE:
            raise RuntimeError("Unrecognised format", self._format, "for V4L2")
        return FORMAT_TABLE[self._format]

    def _start(self):
        self.vd = open('/dev/video11', 'rb+', buffering=0)

        self.buf_available = queue.Queue()
        self.buf_frame = queue.Queue()

        self.thread = threading.Thread(target=self.thread_poll, args=(self.buf_available,))
        self.thread.setDaemon(True)
        self.thread.start()

        cp = v4l2_capability()
        fcntl.ioctl(self.vd, VIDIOC_QUERYCAP, cp)

        if self.bitrate is not None:
            ctrl = v4l2_control()
            ctrl.id = V4L2_CID_MPEG_VIDEO_BITRATE
            ctrl.value = self.bitrate
            fcntl.ioctl(self.vd, VIDIOC_S_CTRL, ctrl)

        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
        fmt.fmt.pix_mp.width = self._width
        fmt.fmt.pix_mp.height = self._height
        fmt.fmt.pix_mp.pixelformat = self._v4l2_format
        fmt.fmt.pix_mp.plane_fmt[0].bytesperline = self.stride
        fmt.fmt.pix_mp.field = V4L2_FIELD_ANY
        fmt.fmt.pix_mp.colorspace = V4L2_COLORSPACE_JPEG
        fmt.fmt.pix_mp.num_planes = 1
        fcntl.ioctl(self.vd, VIDIOC_S_FMT, fmt)

        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
        fmt.fmt.pix_mp.width = self._width
        fmt.fmt.pix_mp.height = self._height
        fmt.fmt.pix_mp.pixelformat = self._pixformat
        fmt.fmt.pix_mp.field = V4L2_FIELD_ANY
        fmt.fmt.pix_mp.colorspace = V4L2_COLORSPACE_DEFAULT
        fmt.fmt.pix_mp.num_planes = 1
        fmt.fmt.pix_mp.plane_fmt[0].bytesperline = 0
        fmt.fmt.pix_mp.plane_fmt[0].sizeimage = 512 << 10
        fcntl.ioctl(self.vd, VIDIOC_S_FMT, fmt)

        if self.framerate is not None and self._enable_framerate:
            # Some codecs, such as H264, support this parameter. Our other codecs do not,
            # and do not allow you to set the framerate property.
            sparm = v4l2_streamparm()
            sparm.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
            sparm.parm.output.capabilities = V4L2_CAP_TIMEPERFRAME
            sparm.parm.output.timeperframe.numerator = 1000
            sparm.parm.output.timeperframe.denominator = round(self.framerate * 1000)
            fcntl.ioctl(self.vd, VIDIOC_S_PARM, sparm)

        if len(self._controls) > 0:
            controlarr = (v4l2_ext_control * len(self._controls))()
            ext = v4l2_ext_controls()
            for i, tup in enumerate(self._controls):
                idv, value = tup
                controlarr[i].id = idv
                controlarr[i].value = value
                controlarr[i].size = 0
            ext.controls = controlarr
            ext.count = len(self._controls)
            ext.ctrl_class = V4L2_CTRL_CLASS_MPEG
            fcntl.ioctl(self.vd, VIDIOC_S_EXT_CTRLS, ext)

        NUM_OUTPUT_BUFFERS = 16
        NUM_CAPTURE_BUFFERS = 16

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
            fcntl.ioctl(self.vd, VIDIOC_QUERYBUF, buffer)
            self.bufs[i] = (mmap.mmap(self.vd.fileno(), buffer.m.planes[0].length,
                                      mmap.PROT_READ | mmap.PROT_WRITE,
                                      mmap.MAP_SHARED, offset=buffer.m.planes[0].m.mem_offset),
                            buffer.m.planes[0].length)
            fcntl.ioctl(self.vd, VIDIOC_QBUF, buffer)

        typev = v4l2_buf_type(V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE)
        fcntl.ioctl(self.vd, VIDIOC_STREAMON, typev)
        typev = v4l2_buf_type(V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE)
        fcntl.ioctl(self.vd, VIDIOC_STREAMON, typev)

    def _stop(self):
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
        """Outputs encoded frames"""
        pollit = select.poll()
        pollit.register(self.vd, select.POLLIN)

        while self._running or self.buf_frame.qsize() > 0:
            events = pollit.poll(400)

            if not events and not self._running:
                # Occasionally it seems to happen on some platforms that, once
                # we stop feeding frames in, the last frames don't get returned
                # to us. Not clear why, but it's better just to give up after a
                # few hundred ms than wait forever. Note that self.buf_frame.qsize()
                # frames (usually just 1) are getting dropped here, and won't be
                # encoded. I've only ever seen this on a Pi Zero.
                while self.buf_frame.qsize() > 0:
                    queue_item = self.buf_frame.get()
                    queue_item.release()
                break

            for _, event in events:
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
                    keyframe = (buf.flags & V4L2_BUF_FLAG_KEYFRAME) != 0

                    if ret == 0:
                        bufindex = buf.index
                        buflen = buf.m.planes[0].length

                        # Write output to file
                        b = self.bufs[buf.index][0].read(buf.m.planes[0].bytesused)
                        self.bufs[buf.index][0].seek(0)
                        self.outputframe(b, keyframe, (buf.timestamp.secs * 1000000) + buf.timestamp.usecs)

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
                        queue_item = self.buf_frame.get()
                        queue_item.release()

    def _encode(self, stream, request):
        """Encodes a frame

        :param stream: Stream
        :param request: Request
        """
        # Don't start encoding if we don't have an output handle
        # as the header seems only to be sent with the first frame
        if self._output is None:
            return
        if self.vd is None or self.vd.closed:
            return
        if isinstance(stream, str):
            stream = request.stream_map[stream]
        cfg = stream.configuration
        fb = request.request.buffers[stream]
        fd = fb.planes[0].fd
        request.acquire()

        buf = v4l2_buffer()
        timestamp_us = self._timestamp(request)

        # Pass frame to video 4 linux, to encode
        planes = v4l2_plane * VIDEO_MAX_PLANES
        planes = planes()
        buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE
        buf.index = self.buf_available.get()
        buf.field = V4L2_FIELD_NONE
        buf.memory = V4L2_MEMORY_DMABUF
        buf.length = 1
        buf.timestamp.secs = timestamp_us // 1000000
        buf.timestamp.usecs = timestamp_us % 1000000
        buf.m.planes = planes
        buf.m.planes[0].m.fd = fd
        buf.m.planes[0].bytesused = cfg.frame_size
        buf.m.planes[0].length = cfg.frame_size
        fcntl.ioctl(self.vd, VIDIOC_QBUF, buf)
        self.buf_frame.put(request)
