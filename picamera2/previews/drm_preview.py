import picamera2.picamera2
import pykms
from picamera2.previews.null_preview import *

class DrmPreview(NullPreview):
    FMT_MAP = {
        "RGB888": pykms.PixelFormat.RGB888,
        "BGR888": pykms.PixelFormat.BGR888,
        # doesn't work "YUYV": pykms.PixelFormat.YUYV,
        # doesn't work "YVYU": pykms.PixelFormat.YVYU,
        "XRGB8888": pykms.PixelFormat.XRGB8888,
        "XBGR8888": pykms.PixelFormat.XBGR8888,
        "YUV420": pykms.PixelFormat.YUV420,
        "YVU420": pykms.PixelFormat.YVU420,
    }

    def __init__(self, picam2, x=0, y=0, width=640, height=480):
        self.init_drm(x, y, width, height)
        self.stop_count = 0
        super().__init__(picam2, width=width, height=height)

    def handle_request(self, picam2):
        completed_request = picam2.process_requests()

        if completed_request:
            self.render_drm(picam2, completed_request)

    def init_drm(self, x, y, width, height):
        self.card = pykms.Card()
        self.resman = pykms.ResourceManager(self.card)
        conn = self.resman.reserve_connector()
        self.crtc = self.resman.reserve_crtc(conn)

        self.plane = None
        self.drmfbs = {}
        self.current = None
        self.window = (x, y, width, height)

    def render_drm(self, picam2, completed_request):
        if picam2.display_stream_name is None:
            return
        stream = picam2.stream_map[picam2.display_stream_name]
        cfg = stream.configuration
        width, height = cfg.size
        fb = completed_request.request.buffers[stream]

        if fb not in self.drmfbs:
            if self.stop_count != picam2.stop_count:
                if picam2.verbose_console:
                    print("Garbage collecting", len(self.drmfbs), "dmabufs")
                self.drmfbs = {}
                self.stop_count = picam2.stop_count

            fmt = self.FMT_MAP[cfg.pixelFormat]
            if self.plane is None:
                self.plane = self.resman.reserve_overlay_plane(self.crtc, fmt)
                if picam2.verbose_console:
                    print("Got plane", self.plane, "for format", fmt)
                assert(self.plane)
            fd = fb.fd(0)
            stride = cfg.stride
            if cfg.pixelFormat in ("YUV420", "YVU420"):
                h2 = height // 2
                stride2 = stride // 2
                size = height * stride
                drmfb = pykms.DmabufFramebuffer(self.card, width, height, fmt,
                                                [fd, fd, fd],
                                                [stride, stride2, stride2],
                                                [0, size, size + h2 * stride2])
            else:
                drmfb = pykms.DmabufFramebuffer(self.card, width, height, fmt, [fd], [stride], [0])
            self.drmfbs[fb] = drmfb
            if picam2.verbose_console:
                print("Made drm fb", drmfb, "for request", completed_request.request)

        drmfb = self.drmfbs[fb]
        x, y, w, h = self.window
        self.crtc.set_plane(self.plane, drmfb, x, y, w, h, 0, 0, width, height)

        if self.current:
            self.current.release()
        self.current = completed_request
