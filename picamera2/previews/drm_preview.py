import gc
import mmap
import threading

import numpy as np

try:
    # If available, use pure python kms package
    import kms as pykms
except ImportError:
    import pykms

from libcamera import Transform

from picamera2.previews.null_preview import *


class DrmManager():
    def __init__(self):
        self.lock = threading.Lock()
        self.use_count = 0

    def add(self, drm_preview):
        with self.lock:
            if self.use_count == 0:
                self.card = pykms.Card()
                self.resman = pykms.ResourceManager(self.card)
                conn = self.resman.reserve_connector()
                self.crtc = self.resman.reserve_crtc(conn)
            self.use_count += 1
        drm_preview.card = self.card
        drm_preview.resman = self.resman
        drm_preview.crtc = self.crtc

    def remove(self, drm_preview):
        drm_preview.card = None
        drm_preview.resman = None
        drm_preview.crtc = None
        with self.lock:
            self.use_count -= 1
            if self.use_count == 0:
                self.crtc = None
                self.resman = None
                self.card = None
                gc.collect()


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
        "MJPEG": pykms.PixelFormat.BGR888,
    }

    _manager = DrmManager()

    def __init__(self, x=0, y=0, width=640, height=480, transform=None):
        self.init_drm(x, y, width, height, transform)
        self.stop_count = 0
        self.fb = pykms.DumbFramebuffer(self.card, width, height, "XB24")
        self.mem = mmap.mmap(self.fb.fd(0), width * height * 3, mmap.MAP_SHARED, mmap.PROT_WRITE)
        self.fd = self.fb.fd(0)
        super().__init__(width=width, height=height)

    def render_request(self, completed_request):
        """Draw the camera image using DRM."""
        with self.lock:
            self.render_drm(self.picam2, completed_request)
            if self.current and self.own_current:
                self.current.release()
            self.current = completed_request
            self.own_current = (completed_request.config['buffer_count'] > 1)
            if self.own_current:
                self.current.acquire()

    def handle_request(self, picam2):
        picam2.process_requests(self)

    def init_drm(self, x, y, width, height, transform):
        DrmPreview._manager.add(self)

        self.plane = None
        self.drmfbs = {}
        self.current = None
        self.own_current = False
        self.window = (x, y, width, height)
        self.transform = Transform() if transform is None else transform
        self.overlay_plane = None
        self.overlay_fb = None
        self.overlay_new_fb = None
        self.lock = threading.Lock()
        self.display_stream_name = None

    def set_overlay(self, overlay):
        if self.picam2 is None:
            raise RuntimeError("Preview must be started before setting an overlay")
        if self.picam2.camera_config is None:
            raise RuntimeError("Preview must be configured before setting an overlay")
        if self.picam2.camera_config['buffer_count'] < 2:
            raise RuntimeError("Need at least buffer_count=2 to set overlay")
        if self.overlay_plane is None:
            raise RuntimeError("Overlays not supported on this device")

        if overlay is None:
            self.overlay_new_fb = None
        else:
            h, w, channels = overlay.shape
            # Should I be recycling these instead of making new ones all the time?
            new_fb = pykms.DumbFramebuffer(self.card, w, h, "AB24")
            with mmap.mmap(new_fb.fd(0), w * h * 4, mmap.MAP_SHARED, mmap.PROT_WRITE) as mm:
                mm.write(np.ascontiguousarray(overlay).data)
            self.overlay_new_fb = new_fb

        if self.picam2.display_stream_name is not None:
            with self.lock:
                self.render_drm(self.picam2, None)

    def render_drm(self, picam2, completed_request):
        if completed_request is not None:
            self.display_stream_name = completed_request.config['display']
            stream = completed_request.stream_map[self.display_stream_name]
        else:
            if self.display_stream_name is None:
                self.display_stream_name = picam2.display_stream_name
            stream = picam2.stream_map[self.display_stream_name]

        cfg = stream.configuration
        pixel_format = str(cfg.pixel_format)
        width, height = (cfg.size.width, cfg.size.height)

        x, y, w, h = self.window
        # Letter/pillar-box to preserve the image's aspect ratio.
        if width * h > w * height:
            new_h = w * height // width
            y += (h - new_h) // 2
            h = new_h
        else:
            new_w = h * width // height
            x += (w - new_w) // 2
            w = new_w

        if self.plane is None:
            if pixel_format not in self.FMT_MAP:
                raise RuntimeError(f"Format {pixel_format} not supported by DRM preview")
            fmt = self.FMT_MAP[pixel_format]

            self.plane = self.resman.reserve_overlay_plane(self.crtc, format=fmt)
            if self.plane is None:
                # Some display devices may not support "alpha".
                self.plane = self.resman.reserve_plane(self.crtc, type=pykms.PlaneType.Primary, format=fmt)
                if self.plane is None:
                    raise RuntimeError("Failed to reserve DRM plane")
            drm_rotation = 1
            if self.transform.hflip:
                drm_rotation |= 16
            if self.transform.vflip:
                drm_rotation |= 32
            try:
                self.plane.set_prop("rotation", drm_rotation)
            except RuntimeError:
                pass
            # The second plane we ask for will go on top of the first.
            self.overlay_plane = self.resman.reserve_overlay_plane(self.crtc, format=pykms.PixelFormat.ABGR8888)
            if self.overlay_plane is not None:
                # Want "coverage" mode, not pre-multiplied alpha. fkms doesn't seem to have this
                # property so we suppress the error, but it seems to have the right behaviour anyway.
                try:
                    self.overlay_plane.set_prop("pixel blend mode", 1)
                except RuntimeError:
                    pass

        # Use an atomic commit for rendering
        ctx = pykms.AtomicReq(self.card)
        if completed_request is not None:
            fb = completed_request.request.buffers[stream]

            if pixel_format == "MJPEG":
                img = completed_request.make_array(self.display_stream_name).tobytes()
                self.mem.seek(0)
                self.mem.write(img)
                fd = self.fd
                stride = width * 3
            else:
                fd = fb.planes[0].fd
                stride = cfg.stride

            if fb not in self.drmfbs:
                if self.stop_count != picam2.stop_count:
                    old_drmfbs = self.drmfbs  # hang on to these until after a new one is sent
                    self.drmfbs = {}
                    self.stop_count = picam2.stop_count
                fmt = self.FMT_MAP[pixel_format]

                if pixel_format in ("YUV420", "YVU420"):
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

            drmfb = self.drmfbs[fb]
            ctx.add_plane(self.plane, drmfb, self.crtc, (0, 0, width, height), (x, y, w, h))

        overlay_new_fb = self.overlay_new_fb
        if overlay_new_fb != self.overlay_fb:
            overlay_old_fb = self.overlay_fb  # Must hang on to this momentarily to avoid a "wink"
            self.overlay_fb = overlay_new_fb
            if self.overlay_fb is not None:
                width, height = self.overlay_fb.width, self.overlay_fb.height
                ctx.add_plane(self.overlay_plane, self.overlay_fb, self.crtc, (0, 0, width, height), (x, y, w, h))
        ctx.commit_sync()
        ctx = None
        overlay_old_fb = None  # noqa  The new one has been sent so it's safe to let this go now
        old_drmfbs = None  # noqa  Can chuck these away now too

    def stop(self):
        super().stop()
        # We may be hanging on to a request, return it to the camera system.
        if self.current is not None and self.own_current:
            self.current.release()
        self.current = None
        self.display_stream_name = None
        # Seem to need some of this in order to be able to create another DrmPreview.
        self.drmfbs = {}
        self.overlay_new_fb = None
        self.overlay_fb = None
        self.plane = None
        self.overlay_plane = None
        self.fd = None
        self.mem = None
        self.fb = None
        DrmPreview._manager.remove(self)
