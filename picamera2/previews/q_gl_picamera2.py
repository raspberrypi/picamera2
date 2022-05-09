from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot, QSocketNotifier
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, pyqtSignal

import sys
import threading
import os
os.environ["PYOPENGL_PLATFORM"] = "egl"

import OpenGL

from OpenGL import GL as gl
from OpenGL.EGL.KHR.image import *
from OpenGL.EGL.EXT.image_dma_buf_import import *
from OpenGL.EGL.VERSION.EGL_1_0 import *
from OpenGL.EGL.VERSION.EGL_1_2 import *
from OpenGL.EGL.VERSION.EGL_1_3 import *

from OpenGL.GLES2.VERSION.GLES2_2_0 import *
from OpenGL.GLES2.OES.EGL_image import *
from OpenGL.GLES2.OES.EGL_image_external import *
from OpenGL.GLES3.VERSION.GLES3_3_0 import *

from OpenGL.GL import shaders

from picamera2.previews.gl_helpers import *


class EglState:
    def __init__(self):
        self.create_display()
        self.choose_config()
        self.create_context()
        # GLES version earlier than 3.0 (e.g. on a Pi 3) don't support this, but it's
        # only a check so we can skip it.
        # check_gl_extensions(["GL_OES_EGL_image"])

    def create_display(self):
        xdisplay = getEGLNativeDisplay()
        self.display = eglGetDisplay(xdisplay)

    def choose_config(self):
        major, minor = EGLint(), EGLint()

        eglInitialize(self.display, major, minor)

        check_egl_extensions(self.display, ["EGL_EXT_image_dma_buf_import"])

        eglBindAPI(EGL_OPENGL_ES_API)

        config_attribs = [
            EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
            EGL_RED_SIZE, 8,
            EGL_GREEN_SIZE, 8,
            EGL_BLUE_SIZE, 8,
            EGL_ALPHA_SIZE, 0,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
            EGL_NONE,
        ]

        n = EGLint()
        configs = (EGLConfig * 1)()
        eglChooseConfig(self.display, config_attribs, configs, 1, n)
        self.config = configs[0]

    def create_context(self):
        context_attribs = [
            EGL_CONTEXT_CLIENT_VERSION, 2,
            EGL_NONE,
        ]

        self.context = eglCreateContext(self.display, self.config, EGL_NO_CONTEXT, context_attribs)

        eglMakeCurrent(self.display, EGL_NO_SURFACE, EGL_NO_SURFACE, self.context)


class QGlPicamera2(QWidget):
    done_signal = pyqtSignal()

    def __init__(self, picam2, parent=None, width=640, height=480):
        super().__init__(parent=parent)
        self.resize(width, height)

        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NativeWindow)

        self.lock = threading.Lock()
        self.count = 0
        self.overlay_present = False
        self.buffers = {}
        self.surface = None
        self.current_request = None
        self.release_current = False
        self.stop_count = 0
        self.egl = EglState()
        if picam2.verbose_console:
            print("EGL {} {}".format(
                eglQueryString(self.egl.display, EGL_VENDOR).decode(),
                eglQueryString(self.egl.display, EGL_VERSION).decode()))
        self.init_gl()

        # set_overlay could be called before the first frame arrives, hence:
        eglMakeCurrent(self.egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)

        self.picamera2 = picam2
        picam2.have_event_loop = True
        self.camera_notifier = QSocketNotifier(self.picamera2.camera_manager.efd,
                                               QtCore.QSocketNotifier.Read,
                                               self)
        self.camera_notifier.activated.connect(self.handle_requests)

    def cleanup(self):
        del self.camera_notifier
        eglDestroySurface(self.egl.display, self.surface)
        self.surface = None
        # We may be hanging on to a request, return it to the camera system.
        if self.current_request is not None and self.release_current:
            self.current_request.release()
        self.current_request = None

    def signal_done(self, picamera2):
        self.done_signal.emit()

    def paintEngine(self):
        return None

    def create_surface(self):
        native_surface = c_void_p(self.winId().__int__())
        surface = eglCreateWindowSurface(self.egl.display, self.egl.config,
                                         native_surface, None)

        self.surface = surface

    def init_gl(self):
        self.create_surface()

        eglMakeCurrent(self.egl.display, self.surface, self.surface, self.egl.context)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.overlay_texture = glGenTextures(1)

        vertShaderSrc = """
            attribute vec2 aPosition;
            varying vec2 texcoord;

            void main()
            {
                gl_Position = vec4(aPosition * 2.0 - 1.0, 0.0, 1.0);
                texcoord.x = aPosition.x;
                texcoord.y = 1.0 - aPosition.y;
            }
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
            shaders.compileShader(vertShaderSrc, GL_VERTEX_SHADER),
            shaders.compileShader(fragShaderSrc_image, GL_FRAGMENT_SHADER)
        )
        self.program_overlay = shaders.compileProgram(
            shaders.compileShader(vertShaderSrc, GL_VERTEX_SHADER),
            shaders.compileShader(fragShaderSrc_overlay, GL_FRAGMENT_SHADER)
        )

        vertPositions = [
            0.0, 0.0,
            1.0, 0.0,
            1.0, 1.0,
            0.0, 1.0
        ]

        inputAttrib = glGetAttribLocation(self.program_image, "aPosition")
        glVertexAttribPointer(inputAttrib, 2, GL_FLOAT, GL_FALSE, 0, vertPositions)
        glEnableVertexAttribArray(inputAttrib)

        inputAttrib = glGetAttribLocation(self.program_overlay, "aPosition")
        glVertexAttribPointer(inputAttrib, 2, GL_FLOAT, GL_FALSE, 0, vertPositions)
        glEnableVertexAttribArray(inputAttrib)

        glUseProgram(self.program_overlay)
        glUniform1i(glGetUniformLocation(self.program_overlay, "overlay"), 0)

    class Buffer:
        # libcamera format string -> DRM fourcc, note that 24-bit formats are not supported
        FMT_MAP = {
            "XRGB8888": "XR24",
            "XBGR8888": "XB24",
            "YUYV": "YUYV",
            # doesn't work "YVYU": "YVYU",
            "UYVY": "UYVY",
            # doesn't work "VYUY": "VYUY",
            "YUV420": "YU12",
            "YVU420": "YV12",
        }

        def __init__(self, display, completed_request):
            picam2 = completed_request.picam2
            stream = picam2.stream_map[picam2.display_stream_name]
            fb = completed_request.request.buffers[stream]

            cfg = stream.configuration
            fmt = cfg.pixelFormat
            if fmt not in self.FMT_MAP:
                raise RuntimeError(f"Format {fmt} not supported by QGlPicamera2 preview")
            fmt = str_to_fourcc(self.FMT_MAP[fmt])
            w, h = cfg.size

            if cfg.pixelFormat in ("YUV420", "YVU420"):
                h2 = h // 2
                stride2 = cfg.stride // 2
                attribs = [
                    EGL_WIDTH, w,
                    EGL_HEIGHT, h,
                    EGL_LINUX_DRM_FOURCC_EXT, fmt,
                    EGL_DMA_BUF_PLANE0_FD_EXT, fb.fd(0),
                    EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                    EGL_DMA_BUF_PLANE0_PITCH_EXT, cfg.stride,
                    EGL_DMA_BUF_PLANE1_FD_EXT, fb.fd(0),
                    EGL_DMA_BUF_PLANE1_OFFSET_EXT, h * cfg.stride,
                    EGL_DMA_BUF_PLANE1_PITCH_EXT, stride2,
                    EGL_DMA_BUF_PLANE2_FD_EXT, fb.fd(0),
                    EGL_DMA_BUF_PLANE2_OFFSET_EXT, h * cfg.stride + h2 * stride2,
                    EGL_DMA_BUF_PLANE2_PITCH_EXT, stride2,
                    EGL_NONE,
                ]
            else:
                attribs = [
                    EGL_WIDTH, w,
                    EGL_HEIGHT, h,
                    EGL_LINUX_DRM_FOURCC_EXT, fmt,
                    EGL_DMA_BUF_PLANE0_FD_EXT, fb.fd(0),
                    EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                    EGL_DMA_BUF_PLANE0_PITCH_EXT, cfg.stride,
                    EGL_NONE,
                ]

            image = eglCreateImageKHR(display,
                                      EGL_NO_CONTEXT,
                                      EGL_LINUX_DMA_BUF_EXT,
                                      None,
                                      attribs)

            self.texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_EXTERNAL_OES, self.texture)
            glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glEGLImageTargetTexture2DOES(GL_TEXTURE_EXTERNAL_OES, image)

            eglDestroyImageKHR(display, image)

    def set_overlay(self, overlay):
        with self.lock:
            if overlay is None:
                self.overlay_present = False
            else:
                # All this swapping round of contexts is a bit icky, but I'd rather copy
                # the overlay here so that the user doesn't have to worry about us still
                # using it after this function returns.
                eglMakeCurrent(self.egl.display, self.surface, self.surface, self.egl.context)
                glBindTexture(GL_TEXTURE_2D, self.overlay_texture)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                (height, width, channels) = overlay.shape
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, overlay)
                eglMakeCurrent(self.egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)
                self.overlay_present = True

    def repaint(self, completed_request):
        with self.lock:
            self.repaint_with_lock(completed_request)

    def repaint_with_lock(self, completed_request):
        eglMakeCurrent(self.egl.display, self.surface, self.surface, self.egl.context)
        if completed_request.request not in self.buffers:
            if self.stop_count != self.picamera2.stop_count:
                if self.picamera2.verbose_console:
                    print("Garbage collect", len(self.buffers), "textures")
                for (req, buffer) in self.buffers.items():
                    glDeleteTextures(1, [buffer.texture])
                self.buffers = {}
                self.stop_count = self.picamera2.stop_count

            if self.picamera2.verbose_console:
                print("Make buffer for request", completed_request.request)
            self.buffers[completed_request.request] = self.Buffer(self.egl.display, completed_request)

        buffer = self.buffers[completed_request.request]

        glUseProgram(self.program_image)
        glBindTexture(GL_TEXTURE_EXTERNAL_OES, buffer.texture)
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

        if self.overlay_present:
            glUseProgram(self.program_overlay)
            glBindTexture(GL_TEXTURE_2D, self.overlay_texture)
            glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

        eglSwapBuffers(self.egl.display, self.surface)

        if self.current_request and self.release_current:
            self.current_request.release()
        self.current_request = completed_request
        eglMakeCurrent(self.egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT)

    @pyqtSlot()
    def handle_requests(self):
        request = self.picamera2.process_requests()
        if request:
            if self.picamera2.display_stream_name is not None:
                self.repaint(request)
                # The pipeline will stall if there's only one buffer and we always hold on to
                # the last one. When we can, however, holding on to them is still preferred.
                if self.picamera2.camera_config['buffer_count'] > 1:
                    self.release_current = True
                else:
                    request.release()
            else:
                request.release()
