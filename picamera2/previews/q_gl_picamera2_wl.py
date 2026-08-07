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
from OpenGL.GLES2.OES.EGL_image import *
from OpenGL.GLES2.OES.EGL_image_external import *
from OpenGL.GLES2.VERSION.GLES2_2_0 import *
from OpenGL.GLES3.VERSION.GLES3_3_0 import *

from picamera2.previews.gl_helpers import _GlRendererMixin, _WaylandGlWidget

from .qt_compatibility import _QT_BINDING, _get_qt_modules


@lru_cache(maxsize=None, typed=False)
def _get_qglpicamera2_wl(qt_module: _QT_BINDING):
    QtCore, QtGui, QtWidgets = _get_qt_modules(qt_module)
    QSocketNotifier, Qt, pyqtSignal, pyqtSlot = attrgetter('QSocketNotifier', 'Qt', 'pyqtSignal', 'pyqtSlot')(QtCore)
    QSurfaceFormat = QtGui.QSurfaceFormat

    # QOpenGLWidget lives in QtWidgets on Qt5 but moved to QtOpenGLWidgets on Qt6.
    if hasattr(QtWidgets, 'QOpenGLWidget'):
        QOpenGLWidget = QtWidgets.QOpenGLWidget
    else:
        import importlib

        QOpenGLWidget = importlib.import_module('.QtOpenGLWidgets', qt_module.value).QOpenGLWidget

    def _gles_format():
        fmt = QSurfaceFormat()
        # samplerExternalOES / GL_OES_EGL_image_external live in GLES.
        try:
            fmt.setRenderableType(QSurfaceFormat.OpenGLES)  # Qt5
        except AttributeError:
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGLES)  # Qt6
        fmt.setVersion(2, 0)
        return fmt

    class QGlPicamera2Wl(QOpenGLWidget, _WaylandGlWidget, _GlRendererMixin):
        done_signal = pyqtSignal(object)

        def __init__(
            self,
            picam2,
            parent=None,
            width=640,
            height=480,
            bg_colour=(20, 20, 20),
            keep_ar=True,
            transform=None,
            preview_window=None,
        ):
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

            self.egl_display = None  # captured from Qt in initializeGL
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

            self.camera_notifier = QSocketNotifier(self.picamera2.notifyme_r, QSocketNotifier.Type.Read, self)
            self.camera_notifier.activated.connect(self.handle_requests)
            self.destroyed.connect(self.cleanup)
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
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            self._gl_ready = True

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

        def cleanup(self):
            if not self.running:
                return
            self.running = False
            self.camera_notifier.deleteLater()
            try:
                self.makeCurrent()
                for _, buffer in self.buffers.items():
                    glDeleteTextures(1, [buffer.texture])
                if self.program_image is not None:
                    glDeleteProgram(self.program_image)
                    self.program_image = None
                if self.program_overlay is not None:
                    glDeleteProgram(self.program_overlay)
                    self.program_overlay = None
                if self.overlay_texture is not None:
                    glDeleteTextures(1, [self.overlay_texture])
                    self.overlay_texture = None
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
