#
# q_gl_picamera2_wl_direct.py - native-Wayland Qt GL viewfinder that renders
# straight to the window surface (no intermediate FBO blit).
#
# QGlPicamera2Wl (q_gl_picamera2_wl.py) uses a QOpenGLWidget, which always
# renders into an offscreen FBO that Qt then composites into the window - one
# extra full-frame GPU blit per frame. This variant uses a QOpenGLWindow
# embedded with QWidget.createWindowContainer(): the QOpenGLWindow owns its own
# native (sub)surface and presents directly via eglSwapBuffers, so there is no
# in-process blit. This restores the directness of the original X11
# QGlPicamera2 (WA_PaintOnScreen) while remaining native Wayland - on Wayland
# Qt backs the QOpenGLWindow with a wl_egl_window, on X11 with an X drawable.
#
# Trade-off: container/native windows always stack above sibling widgets and
# can't be clipped by non-rectangular masks. For a viewfinder that fills its
# area this is fine (overlays are drawn inside this GL context), but apps that
# float Qt widgets over the preview should prefer QGlPicamera2Wl.
#
# The zero-copy dmabuf -> EGLImage -> GL_OES_EGL_image_external path and the
# eglGetCurrentDisplay() trick are identical to QGlPicamera2Wl.
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
def _get_qglpicamera2_wl_direct(qt_module: _QT_BINDING):
    QtCore, QtGui, QtWidgets = _get_qt_modules(qt_module)
    QSocketNotifier, Qt, pyqtSignal, pyqtSlot = attrgetter('QSocketNotifier', 'Qt', 'pyqtSignal', 'pyqtSlot')(QtCore)
    QSurfaceFormat = QtGui.QSurfaceFormat
    QWidget = QtWidgets.QWidget
    QVBoxLayout = QtWidgets.QVBoxLayout

    # QOpenGLWindow is in QtGui on Qt5, QtOpenGL on Qt6.
    if hasattr(QtGui, 'QOpenGLWindow'):
        QOpenGLWindow = QtGui.QOpenGLWindow
    else:
        import importlib

        QOpenGLWindow = importlib.import_module('.QtOpenGL', qt_module.value).QOpenGLWindow

    def _gles_format():
        fmt = QSurfaceFormat()
        try:
            fmt.setRenderableType(QSurfaceFormat.OpenGLES)
        except AttributeError:
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGLES)
        fmt.setVersion(2, 0)
        return fmt

    class _GlWindow(QOpenGLWindow, _GlRendererMixin):
        """The GL surface. Renders directly to its own window - no FBO blit."""

        def __init__(self, picam2, keep_ar, transform, bg_colour):
            super().__init__()
            self.setFormat(_gles_format())
            self.picamera2 = picam2
            self.keep_ar = keep_ar
            self.transform = Transform() if transform is None else transform
            self.bg_colour = [c / 255.0 for c in bg_colour] + [1.0]
            self.lock = threading.Lock()
            self.buffers = {}
            self.current_request = None
            self.own_current = False
            self.stop_count = 0
            self.egl_display = None
            self.max_texture_size = 2048
            self.program_image = None
            self.program_overlay = None
            self.overlay_texture = None
            self.overlay_present = False
            self.overlay_array = None
            self._overlay_dirty = False
            self._gl_ready = False

        def initializeGL(self):
            self.egl_display = eglGetCurrentDisplay()
            n = GLint()
            glGetIntegerv(GL_MAX_TEXTURE_SIZE, n)
            self.max_texture_size = n.value
            self._build_programs()
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            # If we're already exposed (context created after first expose),
            # paint bg_colour and swap immediately so there's no white flash.
            glClearColor(*self.bg_colour)
            glClear(GL_COLOR_BUFFER_BIT)
            if self.isExposed():
                self.context().swapBuffers(self)
            self._gl_ready = True

        def render_request(self, completed_request):
            # Render synchronously, like the original QGlPicamera2: a
            # QOpenGLWindow lets us make its context current and swap from
            # outside paintGL. (Deferred update()/requestUpdate() is throttled
            # to Wayland frame callbacks, which an embedded subsurface may not
            # receive, so it would starve - hence direct rendering here.)
            with self.lock:
                if self.current_request and self.own_current:
                    self.current_request.release()
                self.current_request = completed_request
                self.own_current = completed_request.config['buffer_count'] > 1
                if self.own_current:
                    self.current_request.acquire()
                if self._gl_ready and self.isExposed():
                    self.makeCurrent()
                    self._repaint(self.current_request)
                    self.context().swapBuffers(self)
                    self.doneCurrent()

        def paintGL(self):
            # Called by Qt on expose/resize; Qt swaps for us here.
            if not self._gl_ready:
                return
            with self.lock:
                self._repaint(self.current_request)

        def cleanup_gl(self):
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

    class QGlPicamera2WlDirect(QWidget, _WaylandGlWidget):
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
            self.resize(width, height)
            # Fill the widget background with bg_colour so that while the
            # QOpenGLWindow sub-surface has no committed buffer (transparent),
            # the parent surface shows dark rather than the default white.
            pal = self.palette()
            pal.setColor(QtGui.QPalette.Window, QtGui.QColor(*bg_colour))
            self.setPalette(pal)
            self.setAutoFillBackground(True)
            self.picamera2 = picam2
            self.preview_window = preview_window
            self.title_function = None

            self._glwin = _GlWindow(picam2, keep_ar, transform, bg_colour)
            container = QWidget.createWindowContainer(self._glwin, self)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(container)

            picam2.attach_preview(preview_window)
            self.camera_notifier = QSocketNotifier(self.picamera2.notifyme_r, QSocketNotifier.Type.Read, self)
            self.camera_notifier.activated.connect(self.handle_requests)
            self.destroyed.connect(self.cleanup)
            self.running = True

        def render_request(self, completed_request):
            if self.title_function is not None:
                self.setWindowTitle(self.title_function(completed_request.get_metadata()))
            self._glwin.render_request(completed_request)

        @pyqtSlot()
        def handle_requests(self):
            if not self.running:
                return
            self.picamera2.notifymeread.read()
            self.picamera2.process_requests(self)

        def signal_done(self, job):
            self.done_signal.emit(job)

        def set_overlay(self, overlay):
            self._glwin.set_overlay(overlay)

        def cleanup(self):
            if not self.running:
                return
            self.running = False
            self.camera_notifier.deleteLater()
            self._glwin.cleanup_gl()
            self.picamera2.detach_preview()
            if self.preview_window is not None:
                self.preview_window.qpicamera2 = None

        def closeEvent(self, event):
            self.cleanup()

    return QGlPicamera2WlDirect
