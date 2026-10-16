import os
import threading
import time
from ctypes import c_void_p
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

from picamera2.previews.gl_helpers import Buffer, build_camera_programs, check_egl_extensions, getEGLNativeDisplay

from .qt_compatibility import _QT_BINDING, _get_qt_modules


class EglState:
    def __init__(self):
        self.create_display()
        self.choose_config()
        self.create_context()
        # GLES version earlier than 3.0 (e.g. on a Pi 3) don't support this, but it's
        # only a check so we can skip it.
        # check_gl_extensions(["GL_OES_EGL_image"])
        n = GLint()
        glGetIntegerv(GL_MAX_TEXTURE_SIZE, n)
        self.max_texture_size = n.value

    def create_display(self):
        xdisplay = getEGLNativeDisplay()
        self.display = eglGetDisplay(xdisplay)

    def choose_config(self):
        major, minor = EGLint(), EGLint()

        eglInitialize(self.display, major, minor)

        check_egl_extensions(self.display, ["EGL_EXT_image_dma_buf_import"])

        eglBindAPI(EGL_OPENGL_ES_API)

        # fmt: off
        config_attribs = [
            EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
            EGL_RED_SIZE, 8,
            EGL_GREEN_SIZE, 8,
            EGL_BLUE_SIZE, 8,
            EGL_ALPHA_SIZE, 0,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
            EGL_NONE,
        ]
        # fmt: on

        n = EGLint()
        configs = (EGLConfig * 1)()
        eglChooseConfig(self.display, config_attribs, configs, 1, n)
        self.config = configs[0]

    def create_context(self):
        context_attribs = [EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE]

        self.context = eglCreateContext(self.display, self.config, EGL_NO_CONTEXT, context_attribs)
        eglMakeCurrent(self.display, EGL_NO_SURFACE, EGL_NO_SURFACE, self.context)


@lru_cache(maxsize=None, typed=False)
def _get_qglpicamera2(qt_module: _QT_BINDING):
    # Get Qt modules
    QtCore, QtGui, QtWidgets = _get_qt_modules(qt_module)

    # Get from QtCore
    QSocketNotifier, Qt, pyqtSignal, pyqtSlot = attrgetter('QSocketNotifier', 'Qt', 'pyqtSignal', 'pyqtSlot')(QtCore)

    # Get from QtWidgets
    QWidget = attrgetter('QWidget')(QtWidgets)

    class QGlPicamera2(QWidget):
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

            self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
            self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)

            self.bg_colour = [colour / 255.0 for colour in bg_colour] + [1.0]
            self.keep_ar = keep_ar
            self.transform = Transform() if transform is None else transform
            self.lock = threading.Lock()
            self.count = 0
            self.overlay_present = False
            self.buffers = {}
            self.surface = None
            self.current_request = None
            self.own_current = False
            self.stop_count = 0
            self.title_function = None
            self.egl = EglState()
            if picam2.verbose_console:
                print(
                    f"EGL {eglQueryString(self.egl.display, EGL_VENDOR).decode()} "
                    f"{eglQueryString(self.egl.display, EGL_VERSION).decode()}"
                )
            self.init_gl()

            # set_overlay could be called before the first frame arrives, hence:
            eglMakeCurrent(self.egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)

            self.picamera2 = picam2
            picam2.attach_preview(preview_window)
            self.preview_window = preview_window

            self.camera_notifier = QSocketNotifier(self.picamera2.notifyme_r, QSocketNotifier.Type.Read, self)
            self.camera_notifier.activated.connect(self.handle_requests)
            # Must always run cleanup when this widget goes away.
            self.destroyed.connect(lambda: self.cleanup())
            self.running = True

        def cleanup(self):
            if not self.running:
                return
            self.running = False
            self.camera_notifier.deleteLater()
            eglDestroySurface(self.egl.display, self.surface)
            self.surface = None
            # We may be hanging on to a request, return it to the camera system.
            if self.current_request is not None and self.own_current:
                self.current_request.release()
            self.current_request = None
            # We have to tell both the preview window and the Picamera2 object that we have
            # disappeared.
            self.picamera2.detach_preview()
            if self.preview_window is not None:  # will be none when a proper Qt app
                self.preview_window.qpicamera2 = None

            # Some extra EGL cleanup seems to be required.
            for _, buffer in self.buffers.items():
                glDeleteTextures(1, [buffer.texture])
            self.buffers = {}
            eglDestroyContext(self.egl.display, self.egl.context)
            self.egl.context = None

        def closeEvent(self, event):
            self.cleanup()

        def signal_done(self, job):
            self.done_signal.emit(job)

        def paintEngine(self):
            return None

        def create_surface(self):
            native_surface = c_void_p(self.winId().__int__())
            surface = eglCreateWindowSurface(self.egl.display, self.egl.config, native_surface, None)

            self.surface = surface

        def init_gl(self):
            self.create_surface()

            eglMakeCurrent(self.egl.display, self.surface, self.surface, self.egl.context)

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            (self.program_image, self.program_overlay, self._vertPositions, self.overlay_texture) = build_camera_programs(
                self.transform
            )

        def set_overlay(self, overlay):
            if not self.picamera2.camera_config:
                raise RuntimeError("Camera must be configured before setting overlay")
            if self.picamera2.camera_config['buffer_count'] < 2:
                raise RuntimeError("Need at least buffer_count=2 to set overlay")

            with self.lock:
                eglMakeCurrent(self.egl.display, self.surface, self.surface, self.egl.context)

                if overlay is None:
                    self.overlay_present = False
                    self.repaint(self.current_request)
                else:
                    # All this swapping round of contexts is a bit icky, but I'd rather copy
                    # the overlay here so that the user doesn't have to worry about us still
                    # using it after this function returns.
                    glBindTexture(GL_TEXTURE_2D, self.overlay_texture)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                    (height, width, channels) = overlay.shape
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, overlay)
                    self.overlay_present = True
                    self.repaint(self.current_request)

                eglMakeCurrent(self.egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)

        def repaint(self, completed_request, update_viewport=False):
            # The context should be set up and cleared by the caller.
            if completed_request and completed_request.request not in self.buffers:
                if self.stop_count != self.picamera2.stop_count:
                    if self.picamera2.verbose_console:
                        print("Garbage collect", len(self.buffers), "textures")
                    for _, buffer in self.buffers.items():
                        glDeleteTextures(1, [buffer.texture])
                    self.buffers = {}
                    self.stop_count = self.picamera2.stop_count

                if self.picamera2.verbose_console:
                    print("Make buffer for request", completed_request.request)
                self.buffers[completed_request.request] = Buffer(
                    self.egl.display, completed_request, self.egl.max_texture_size
                )

                # New buffers mean the image size may change so update the viewport just in case.
                update_viewport = True

            # If there's no request, then the viewport may never have been set up, so force it anyway.
            if update_viewport or not completed_request:
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

            eglSwapBuffers(self.egl.display, self.surface)

        def render_request(self, completed_request):
            """Draw the camera image using Qt and OpenGL/GLES."""
            # For reasons not terribly well understood, eglMakeCurrent hangs in the X-Wayland world if the
            # window is being closed. This appears to stop it.
            if not self.isVisible():
                return
            if self.title_function is not None:
                self.setWindowTitle(self.title_function(completed_request.get_metadata()))
            with self.lock:
                if self.running:
                    eglMakeCurrent(self.egl.display, self.surface, self.surface, self.egl.context)
                    self.repaint(completed_request)
                    eglMakeCurrent(self.egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)
                if self.current_request and self.own_current:
                    self.current_request.release()
                self.current_request = completed_request
                self.own_current = completed_request.config['buffer_count'] > 1
                if self.own_current:
                    self.current_request.acquire()

        @pyqtSlot()
        def handle_requests(self):
            if not self.running:
                return
            self.picamera2.notifymeread.read()
            self.picamera2.process_requests(self)

        def recalculate_viewport(self):
            window_w = self.width()
            window_h = self.height()

            stream_map = self.picamera2.stream_map
            camera_config = self.picamera2.camera_config
            if not self.keep_ar or not camera_config or camera_config['display'] is None:
                return 0, 0, window_w, window_h

            image_w, image_h = (
                stream_map[camera_config['display']].configuration.size.width,
                stream_map[camera_config['display']].configuration.size.height,
            )
            if image_w * window_h > window_w * image_h:
                w = window_w
                h = w * image_h // image_w
            else:
                h = window_h
                w = h * image_w // image_h
            x_off = (window_w - w) // 2
            y_off = (window_h - h) // 2
            return x_off, y_off, w, h

        def resizeEvent(self, event):
            with self.lock:
                eglMakeCurrent(self.egl.display, self.surface, self.surface, self.egl.context)
                self.repaint(self.current_request, update_viewport=True)
                eglMakeCurrent(self.egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)

        def show(self):
            super().show()
            # We seem to need a short delay before rendering the background colour works. No idea why.
            time.sleep(0.05)
            self.resizeEvent(None)

    return QGlPicamera2


# Define QGlPicamera2 class for compatability
try:
    QPicamera2 = _get_qglpicamera2(_QT_BINDING.PyQt5)
except ImportError:
    pass
