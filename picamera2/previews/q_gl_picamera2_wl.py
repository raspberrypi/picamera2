#
# q_gl_picamera2_wl.py - a GPU-accelerated Qt viewfinder that works on native
# Wayland (as well as X11), unlike QGlPicamera2.
#
# QGlPicamera2 renders raw EGL straight onto the widget's native window
# (WA_PaintOnScreen + eglCreateWindowSurface(winId())). That contract only
# holds on X11, where winId() is an X window; on Wayland eglCreateWindowSurface
# needs a wl_egl_window, and no Qt binding exposes the per-window wl_surface to
# build one. So on Wayland QGlPicamera2 can only run through XWayland.
#
# This widget side-steps that by rendering through Qt's own GL context
# (QOpenGLWidget): Qt creates and owns the platform surface (the wl_egl_window
# on Wayland, the GLX/EGL drawable on X11), and we just draw inside paintGL().
# The only thing the zero-copy dmabuf path needs is an EGLDisplay to import the
# camera buffer on - and inside paintGL Qt's context is current, so
# eglGetCurrentDisplay() hands us the right display on either platform. No
# wl_surface, no platform branching, no private Qt APIs.
#
# Trade-off vs QGlPicamera2: QOpenGLWidget renders into an FBO that Qt then
# composites into the window, i.e. one extra full-frame blit. For a viewfinder
# that is fine, and it is the price of being platform-portable.
#
import os
import threading
from functools import lru_cache
from operator import attrgetter

os.environ["PYOPENGL_PLATFORM"] = "egl"

from libcamera import Transform
from OpenGL.EGL.EXT.image_dma_buf_import import *
from OpenGL.EGL.KHR.image import *
from OpenGL.EGL.VERSION.EGL_1_0 import *
from OpenGL.EGL.VERSION.EGL_1_2 import *
from OpenGL.EGL.VERSION.EGL_1_3 import *
from OpenGL.GL import shaders
from OpenGL.GLES2.OES.EGL_image import *
from OpenGL.GLES2.OES.EGL_image_external import *
from OpenGL.GLES2.VERSION.GLES2_2_0 import *
from OpenGL.GLES3.VERSION.GLES3_3_0 import *

from picamera2.previews.gl_helpers import *

from .qt_compatibility import _QT_BINDING, _get_qt_modules


@lru_cache(maxsize=None, typed=False)
def _get_qglpicamera2_wl(qt_module: _QT_BINDING):
    QtCore, QtGui, QtWidgets = _get_qt_modules(qt_module)
    QSocketNotifier, Qt, pyqtSignal, pyqtSlot = attrgetter(
        'QSocketNotifier', 'Qt', 'pyqtSignal', 'pyqtSlot')(QtCore)
    QSurfaceFormat = QtGui.QSurfaceFormat

    # QOpenGLWidget lives in QtWidgets on Qt5 but moved to QtOpenGLWidgets on Qt6.
    if hasattr(QtWidgets, 'QOpenGLWidget'):
        QOpenGLWidget = QtWidgets.QOpenGLWidget
    else:
        import importlib
        QOpenGLWidget = importlib.import_module(
            '.QtOpenGLWidgets', qt_module.value).QOpenGLWidget

    def _gles_format():
        fmt = QSurfaceFormat()
        # samplerExternalOES / GL_OES_EGL_image_external live in GLES.
        try:
            fmt.setRenderableType(QSurfaceFormat.OpenGLES)               # Qt5
        except AttributeError:
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGLES)  # Qt6
        fmt.setVersion(3, 1)
        return fmt

    class QGlPicamera2Wl(QOpenGLWidget):
        done_signal = pyqtSignal(object)

        def __init__(self, picam2, parent=None, width=640, height=480,
                     bg_colour=(20, 20, 20), keep_ar=True, transform=None,
                     preview_window=None):
            super().__init__(parent=parent)
            self.setFormat(_gles_format())
            self.resize(width, height)

            self.bg_colour = [colour / 255.0 for colour in bg_colour] + [1.0]
            self.keep_ar = keep_ar
            self.transform = Transform() if transform is None else transform
            self.lock = threading.Lock()
            self.buffers = {}
            self.current_request = None
            self.own_current = False
            self.stop_count = 0
            self.title_function = None

            self.egl_display = None        # captured from Qt in initializeGL
            self.max_texture_size = 2048
            self.program_image = None
            self.program_overlay = None
            self.overlay_texture = None
            self.overlay_present = False
            self.overlay_array = None
            self._overlay_dirty = False
            self._gl_ready = False

            self.picamera2 = picam2
            picam2.attach_preview(preview_window)
            self.preview_window = preview_window

            self.camera_notifier = QSocketNotifier(
                self.picamera2.notifyme_r, QSocketNotifier.Type.Read, self)
            self.camera_notifier.activated.connect(self.handle_requests)
            self.destroyed.connect(lambda: self.cleanup())
            self.running = True

        # ------------------------------------------------------------------
        # GL setup - runs with Qt's context current.
        # ------------------------------------------------------------------
        def initializeGL(self):
            # Qt's context is current here, so this is Qt's EGLDisplay (the
            # Wayland one under Wayland, the X11 one under X11/XWayland).
            self.egl_display = eglGetCurrentDisplay()
            n = GLint()
            glGetIntegerv(GL_MAX_TEXTURE_SIZE, n)
            self.max_texture_size = n.value
            self._build_programs()
            self._gl_ready = True

        def _build_programs(self):
            vertShaderSrc_image = f"""
                attribute vec2 aPosition;
                varying vec2 texcoord;
                void main()
                {{
                    gl_Position = vec4(aPosition * 2.0 - 1.0, 0.0, 1.0);
                    texcoord.x = {'1.0 - ' if self.transform.hflip else ''}aPosition.x;
                    texcoord.y = {'' if self.transform.vflip else '1.0 - '}aPosition.y;
                }}
            """
            fragShaderSrc_image = """
                #extension GL_OES_EGL_image_external : enable
                precision mediump float;
                varying vec2 texcoord;
                uniform samplerExternalOES texture;
                void main()
                {
                    gl_FragColor = texture2D(texture, texcoord);
                }
            """
            vertShaderSrc_overlay = """
                attribute vec2 aPosition;
                varying vec2 texcoord;
                void main()
                {
                    gl_Position = vec4(aPosition * 2.0 - 1.0, 0.0, 1.0);
                    texcoord.x = aPosition.x;
                    texcoord.y = 1.0 - aPosition.y;
                }
            """
            fragShaderSrc_overlay = """
                precision mediump float;
                varying vec2 texcoord;
                uniform sampler2D overlay;
                void main()
                {
                    gl_FragColor = texture2D(overlay, texcoord);
                }
            """
            self.program_image = shaders.compileProgram(
                shaders.compileShader(vertShaderSrc_image, GL_VERTEX_SHADER),
                shaders.compileShader(fragShaderSrc_image, GL_FRAGMENT_SHADER))
            self.program_overlay = shaders.compileProgram(
                shaders.compileShader(vertShaderSrc_overlay, GL_VERTEX_SHADER),
                shaders.compileShader(fragShaderSrc_overlay, GL_FRAGMENT_SHADER))

            # Client-side vertex array (allowed in GLES); keep a ref alive.
            self._vertPositions = [0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
            for prog in (self.program_image, self.program_overlay):
                loc = glGetAttribLocation(prog, "aPosition")
                glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, 0,
                                      self._vertPositions)
                glEnableVertexAttribArray(loc)
            glUseProgram(self.program_overlay)
            glUniform1i(glGetUniformLocation(self.program_overlay, "overlay"), 0)
            self.overlay_texture = glGenTextures(1)

        # ------------------------------------------------------------------
        # dmabuf -> EGLImage -> external texture (identical to QGlPicamera2).
        # ------------------------------------------------------------------
        class Buffer:
            FMT_MAP = {
                "XRGB8888": "XR24",
                "XBGR8888": "XB24",
                "YUYV": "YUYV",
                # doesn't work "YVYU": "YVYU",
                "UYVY": "UYVY",
                # doesn't work "VYUY": "VYUY",
                "YUV420": "YU12",
                "YVU420": "YV12",
                "NV12": "NV12",
            }

            def __init__(self, display, completed_request, max_texture_size):
                picam2 = completed_request.picam2
                stream = picam2.stream_map[picam2.display_stream_name]
                fb = completed_request.request.buffers[stream]
                cfg = stream.configuration
                pixel_format = str(cfg.pixel_format)
                if pixel_format not in self.FMT_MAP:
                    raise RuntimeError(
                        f"Format {pixel_format} not supported by QGlPicamera2Wl preview")
                fmt = str_to_fourcc(self.FMT_MAP[pixel_format])
                w, h = (cfg.size.width, cfg.size.height)
                if w > max_texture_size or h > max_texture_size:
                    raise RuntimeError(
                        f"Maximum supported preview image size is {max_texture_size}")
                if pixel_format in ("YUV420", "YVU420"):
                    h2 = h // 2
                    stride2 = cfg.stride // 2
                    attribs = [
                        # fmt: off
                        EGL_WIDTH, w, EGL_HEIGHT, h,
                        EGL_LINUX_DRM_FOURCC_EXT, fmt,
                        EGL_DMA_BUF_PLANE0_FD_EXT, fb.planes[0].fd,
                        EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                        EGL_DMA_BUF_PLANE0_PITCH_EXT, cfg.stride,
                        EGL_DMA_BUF_PLANE1_FD_EXT, fb.planes[0].fd,
                        EGL_DMA_BUF_PLANE1_OFFSET_EXT, h * cfg.stride,
                        EGL_DMA_BUF_PLANE1_PITCH_EXT, stride2,
                        EGL_DMA_BUF_PLANE2_FD_EXT, fb.planes[0].fd,
                        EGL_DMA_BUF_PLANE2_OFFSET_EXT, h * cfg.stride + h2 * stride2,
                        EGL_DMA_BUF_PLANE2_PITCH_EXT, stride2,
                        EGL_NONE,
                    ]
                    # fmt: on
                elif pixel_format == "NV12":
                    h2 = h // 2
                    # fmt: off
                    attribs = [
                        EGL_WIDTH, w,
                        EGL_HEIGHT, h,
                        EGL_LINUX_DRM_FOURCC_EXT, fmt,
                        EGL_DMA_BUF_PLANE0_FD_EXT, fb.planes[0].fd,
                        EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                        EGL_DMA_BUF_PLANE0_PITCH_EXT, cfg.stride,
                        EGL_DMA_BUF_PLANE1_FD_EXT, fb.planes[0].fd,
                        EGL_DMA_BUF_PLANE1_OFFSET_EXT, h * cfg.stride,
                        EGL_DMA_BUF_PLANE1_PITCH_EXT, cfg.stride,
                        EGL_NONE,
                    ]
                    # fmt: on
                else:
                    # fmt: off
                    attribs = [
                        EGL_WIDTH, w, EGL_HEIGHT, h,
                        EGL_LINUX_DRM_FOURCC_EXT, fmt,
                        EGL_DMA_BUF_PLANE0_FD_EXT, fb.planes[0].fd,
                        EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                        EGL_DMA_BUF_PLANE0_PITCH_EXT, cfg.stride,
                        EGL_NONE,
                    ]
                    # fmt: on

                image = eglCreateImageKHR(display, EGL_NO_CONTEXT,
                                          EGL_LINUX_DMA_BUF_EXT, None, attribs)
                self.texture = glGenTextures(1)
                glBindTexture(GL_TEXTURE_EXTERNAL_OES, self.texture)
                glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                glEGLImageTargetTexture2DOES(GL_TEXTURE_EXTERNAL_OES, image)
                eglDestroyImageKHR(display, image)

        # ------------------------------------------------------------------
        # Painting - Qt makes the context current and presents the FBO.
        # ------------------------------------------------------------------
        def paintGL(self):
            if not self._gl_ready:
                return
            with self.lock:
                self._repaint(self.current_request)

        def resizeGL(self, w, h):
            # Qt has already resized our FBO and will call paintGL after this;
            # repaint here too so a resize while the stream is paused (no new
            # camera frame) still updates the viewport/letterboxing. The
            # viewport is recomputed from the live widget size every repaint,
            # so this covers window drags and output/scale changes.
            if self._gl_ready:
                with self.lock:
                    self._repaint(self.current_request)

        def _repaint(self, completed_request):
            if completed_request and completed_request.request not in self.buffers:
                if self.stop_count != self.picamera2.stop_count:
                    for _, buffer in self.buffers.items():
                        glDeleteTextures(1, [buffer.texture])
                    self.buffers = {}
                    self.stop_count = self.picamera2.stop_count
                self.buffers[completed_request.request] = self.Buffer(
                    self.egl_display, completed_request, self.max_texture_size)

            if self._overlay_dirty and self.overlay_array is not None:
                glBindTexture(GL_TEXTURE_2D, self.overlay_texture)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                height, width, _ = self.overlay_array.shape
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, self.overlay_array)
                self._overlay_dirty = False

            x_off, y_off, w, h = self.recalculate_viewport()
            glViewport(x_off, y_off, w, h)
            glClearColor(*self.bg_colour)
            glClear(GL_COLOR_BUFFER_BIT)

            if completed_request:
                buffer = self.buffers[completed_request.request]
                glUseProgram(self.program_image)
                glBindTexture(GL_TEXTURE_EXTERNAL_OES, buffer.texture)
                glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

            if self.overlay_present:
                glUseProgram(self.program_overlay)
                glBindTexture(GL_TEXTURE_2D, self.overlay_texture)
                glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
            # No eglSwapBuffers: QOpenGLWidget presents its FBO for us.

        def recalculate_viewport(self):
            dpr = self.devicePixelRatioF()
            window_w = int(self.width() * dpr)
            window_h = int(self.height() * dpr)
            stream_map = self.picamera2.stream_map
            camera_config = self.picamera2.camera_config
            if not self.keep_ar or not camera_config or camera_config['display'] is None:
                return 0, 0, window_w, window_h
            image_w = stream_map[camera_config['display']].configuration.size.width
            image_h = stream_map[camera_config['display']].configuration.size.height
            if image_w * window_h > window_w * image_h:
                w = window_w
                h = w * image_h // image_w
            else:
                h = window_h
                w = h * image_w // image_h
            return (window_w - w) // 2, (window_h - h) // 2, w, h

        # ------------------------------------------------------------------
        # Camera frames arrive on the GUI thread (via the QSocketNotifier),
        # so we just stash the request and schedule a repaint; the GL work
        # happens in paintGL with Qt's context current.
        # ------------------------------------------------------------------
        def render_request(self, completed_request):
            if self.title_function is not None:
                self.setWindowTitle(self.title_function(completed_request.get_metadata()))
            with self.lock:
                if self.current_request and self.own_current:
                    self.current_request.release()
                self.current_request = completed_request
                self.own_current = completed_request.config['buffer_count'] > 1
                if self.own_current:
                    self.current_request.acquire()
            self.update()

        @pyqtSlot()
        def handle_requests(self):
            if not self.running:
                return
            self.picamera2.notifymeread.read()
            self.picamera2.process_requests(self)

        def signal_done(self, job):
            self.done_signal.emit(job)

        def set_overlay(self, overlay):
            with self.lock:
                self.overlay_array = overlay
                self.overlay_present = overlay is not None
                self._overlay_dirty = overlay is not None
            self.update()

        def cleanup(self):
            if not self.running:
                return
            self.running = False
            self.camera_notifier.deleteLater()
            try:
                self.makeCurrent()
                for _, buffer in self.buffers.items():
                    glDeleteTextures(1, [buffer.texture])
                self.doneCurrent()
            except Exception:
                pass
            self.buffers = {}
            if self.current_request is not None and self.own_current:
                self.current_request.release()
            self.current_request = None
            self.picamera2.detach_preview()
            if self.preview_window is not None:
                self.preview_window.qpicamera2 = None

        def closeEvent(self, event):
            self.cleanup()

    return QGlPicamera2Wl
