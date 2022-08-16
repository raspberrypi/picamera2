import mmap
import threading
from libcamera import PixelFormat, Transform

import numpy as np
import pykms

import picamera2.picamera2
from picamera2.previews.null_preview import *

dd = None

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

    def __init__(self, x=0, y=0, width=640, height=480, transform=None):
        self.init_drm(x, y, width, height, transform)
        self.stop_count = 0
        super().__init__(width=width, height=height)

    def handle_request(self, picam2):
        completed_request = picam2.process_requests()
        if completed_request:
            if picam2.display_stream_name is not None:
                with self.lock:
                    self.render_drm(picam2, completed_request)
                    if self.current and self.own_current:
                        self.current.release()
                    self.current = completed_request
                # The pipeline will stall if there's only one buffer and we always hold on to
                # the last one. When we can, however, holding on to them is still preferred.
                config = picam2.camera_config
                if config is not None and config['buffer_count'] > 1:
                    self.own_current = True
                else:
                    self.own_current = False
                    completed_request.release()
            else:
                completed_request.release()

    def init_drm(self, x, y, width, height, transform):
        self.card = pykms.Card()
        self.resman = pykms.ResourceManager(self.card)
        conn = self.resman.reserve_connector()
        self.crtc = self.resman.reserve_crtc(conn)

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

    def set_overlay(self, overlay):
        if self.picam2 is None:
            raise RuntimeError("Preview must be started before settings an overlay")

        if overlay is None:
            self.overlay_new_fb = None
        else:
            h, w, channels = overlay.shape
            # Should I be recycling these instead of making new ones all the time?
            new_fb = pykms.DumbFramebuffer(self.card, w, h, "AB24")
            with mmap.mmap(new_fb.fd(0), w * h * 4, mmap.MAP_SHARED, mmap.PROT_WRITE) as mm:
                mm.write(np.ascontiguousarray(overlay).data)
            self.overlay_new_fb = new_fb

        with self.lock:
            self.render_drm(self.picam2, self.current)

    def render_drm(self, picam2, completed_request):
        if picam2.display_stream_name is None:
            return
        stream = picam2.stream_map[picam2.display_stream_name]
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

            self.plane = self.resman.reserve_overlay_plane(self.crtc, fmt)
            if self.plane is None:
                raise RuntimeError("Failed to reserve DRM plane")
            drm_rotation = 1
            if self.transform.hflip:
                drm_rotation |= 16
            if self.transform.vflip:
                drm_rotation |= 32
            self.plane.set_prop("rotation", drm_rotation)
            # The second plane we ask for will go on top of the first.
            self.overlay_plane = self.resman.reserve_overlay_plane(self.crtc, pykms.PixelFormat.ABGR8888)
            if self.overlay_plane is None:
                raise RuntimeError("Failed to reserve DRM overlay plane")
            # Want "coverage" mode, not pre-multiplied alpha.
            self.overlay_plane.set_prop("pixel blend mode", 1)

        if completed_request is not None:
            fb = completed_request.request.buffers[stream]
            if fb not in self.drmfbs:
                if self.stop_count != picam2.stop_count:
                    if picam2.verbose_console:
                        print("Garbage collecting", len(self.drmfbs), "dmabufs")
                    old_drmfbs = self.drmfbs  # hang on to these until after a new one is sent
                    self.drmfbs = {}
                    self.stop_count = picam2.stop_count

                fmt = self.FMT_MAP[pixel_format]
                fd = fb.planes[0].fd
                stride = cfg.stride
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
                if picam2.verbose_console:
                    print("Made drm fb", drmfb, "for request", completed_request.request)

            drmfb = self.drmfbs[fb]
            self.crtc.set_plane(self.plane, drmfb, x, y, w, h, 0, 0, width, height)
            # An "atomic commit" would probably be better, but I can't get this to work...
            # ctx = pykms.AtomicReq(self.card)
            # ctx.add(self.plane, {"FB_ID": drmfb.id, "CRTC_ID": self.crtc.id,
            #                      "SRC_W": width << 16, "SRC_H": height << 16,
            #                      "CRTC_X": x, "CRTC_Y": y, "CRTC_W": w, "CRTC_H": h})
            # ctx.commit()

        overlay_new_fb = self.overlay_new_fb
        if overlay_new_fb != self.overlay_fb:
            overlay_old_fb = self.overlay_fb  # Must hang on to this momentarily to avoid a "wink"
            self.overlay_fb = overlay_new_fb
        if self.overlay_fb is not None:
            width, height = self.overlay_fb.width, self.overlay_fb.height
            self.crtc.set_plane(self.overlay_plane, self.overlay_fb, x, y, w, h, 0, 0, width, height)
        overlay_old_fb = None  # The new one has been sent so it's safe to let this go now
        old_drmfbs = None  # Can chuck these away now too

    def stop(self):
        super().stop()
        # We may be hanging on to a request, return it to the camera system.
        if self.current is not None and self.own_current:
            self.current.release()
        self.current = None
        # Seem to need some of this in order to be able to create another DrmPreview.
        self.drmfbs = {}
        self.overlay_new_fb = None
        self.overlay_fb = None
        self.crtc = None
        self.resman = None
        self.card = None
