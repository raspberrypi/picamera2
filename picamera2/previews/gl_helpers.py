from ctypes import CFUNCTYPE, POINTER, c_bool, c_char_p, c_int, c_void_p, cdll, pointer, util

from OpenGL import GL as gl
from OpenGL.EGL.EXT.image_dma_buf_import import *
from OpenGL.EGL.KHR.image import *
from OpenGL.EGL.VERSION.EGL_1_0 import *
from OpenGL.EGL.VERSION.EGL_1_0 import EGLNativeDisplayType, eglGetProcAddress, eglQueryString
from OpenGL.GL import shaders as _shaders
from OpenGL.GLES2.OES.EGL_image_external import *
from OpenGL.GLES2.VERSION.GLES2_2_0 import *
from OpenGL.GLES3.VERSION.GLES3_3_0 import *
from OpenGL.raw.GLES2 import _types as _cs


def getEGLNativeDisplay():
    _x11lib = cdll.LoadLibrary(util.find_library("X11"))
    XOpenDisplay = _x11lib.XOpenDisplay
    XOpenDisplay.argtypes = [c_char_p]
    XOpenDisplay.restype = POINTER(EGLNativeDisplayType)

    _ = XOpenDisplay(None)


# Hack. PyOpenGL doesn't seem to manage to find glEGLImageTargetTexture2DOES.
def getglEGLImageTargetTexture2DOES():
    funcptr = eglGetProcAddress("glEGLImageTargetTexture2DOES")
    prototype = CFUNCTYPE(None, _cs.GLenum, _cs.GLeglImageOES)
    return prototype(funcptr)


glEGLImageTargetTexture2DOES = getglEGLImageTargetTexture2DOES()


def compile_program(vert_src, frag_src):
    """Compile and link a GLES shader program.

    Unlike shaders.compileProgram this skips glValidateProgram (which is
    state-dependent and gives false negatives during initializeGL when no
    textures are bound) and calls glDeleteShader after linking so the
    intermediate shader objects are freed immediately rather than leaking.
    """
    vert = _shaders.compileShader(vert_src, GL_VERTEX_SHADER)
    frag = _shaders.compileShader(frag_src, GL_FRAGMENT_SHADER)
    prog = glCreateProgram()
    if not prog:
        glDeleteShader(vert)
        glDeleteShader(frag)
        raise RuntimeError("glCreateProgram returned 0 — GL context may be invalid or GPU resources exhausted")
    glAttachShader(prog, vert)
    glAttachShader(prog, frag)
    glLinkProgram(prog)
    if not glGetProgramiv(prog, GL_LINK_STATUS):
        info = glGetProgramInfoLog(prog)
        glDeleteProgram(prog)
        glDeleteShader(vert)
        glDeleteShader(frag)
        raise RuntimeError(f"Shader link failed: {info}")
    glDetachShader(prog, vert)
    glDetachShader(prog, frag)
    glDeleteShader(vert)
    glDeleteShader(frag)
    return prog


def build_camera_programs(transform):
    """Compile the GLES camera and overlay programs, set up vertex arrays, and
    allocate the overlay texture.  Must be called with a GL context current.

    Returns (program_image, program_overlay, vert_positions, overlay_texture).
    vert_positions must be kept alive by the caller (GLES client-side array).
    """
    vert_image = f"""
        attribute vec2 aPosition;
        varying vec2 texcoord;
        void main()
        {{
            gl_Position = vec4(aPosition * 2.0 - 1.0, 0.0, 1.0);
            texcoord.x = {'1.0 - ' if transform.hflip else ''}aPosition.x;
            texcoord.y = {'' if transform.vflip else '1.0 - '}aPosition.y;
        }}
    """
    frag_image = """
        #extension GL_OES_EGL_image_external : enable
        precision mediump float;
        varying vec2 texcoord;
        uniform samplerExternalOES texture;
        void main()
        {
            gl_FragColor = texture2D(texture, texcoord);
        }
    """
    vert_overlay = """
        attribute vec2 aPosition;
        varying vec2 texcoord;
        void main()
        {
            gl_Position = vec4(aPosition * 2.0 - 1.0, 0.0, 1.0);
            texcoord.x = aPosition.x;
            texcoord.y = 1.0 - aPosition.y;
        }
    """
    frag_overlay = """
        precision mediump float;
        varying vec2 texcoord;
        uniform sampler2D overlay;
        void main()
        {
            gl_FragColor = texture2D(overlay, texcoord);
        }
    """
    program_image = compile_program(vert_image, frag_image)
    program_overlay = compile_program(vert_overlay, frag_overlay)

    # fmt: off
    vert_positions = [0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
    # fmt: on
    for prog in (program_image, program_overlay):
        loc = glGetAttribLocation(prog, "aPosition")
        glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, 0, vert_positions)
        glEnableVertexAttribArray(loc)
    glUseProgram(program_overlay)
    glUniform1i(glGetUniformLocation(program_overlay, "overlay"), 0)

    overlay_texture = glGenTextures(1)
    return program_image, program_overlay, vert_positions, overlay_texture


class _WaylandGlWidget:
    """Marker: widget uses a native-Wayland GL context.

    Both QGlPicamera2Wl and QGlPicamera2WlDirect inherit this class so that
    is_wayland_gl_widget() can identify either with a single isinstance check.
    """


class _GlRendererMixin:
    """Shared rendering logic for Qt-managed GL contexts (QOpenGLWidget / QOpenGLWindow).

    Provides _build_programs, _repaint, recalculate_viewport, and set_overlay.
    The host class __init__ must set: picamera2, transform, bg_colour, keep_ar,
    lock, buffers, stop_count, egl_display, max_texture_size, program_image,
    program_overlay, overlay_texture, overlay_present, overlay_array, _overlay_dirty.
    """

    def _build_programs(self):
        (self.program_image, self.program_overlay, self._vertPositions, self.overlay_texture) = build_camera_programs(
            self.transform
        )

    def _repaint(self, completed_request):
        if completed_request and completed_request.request not in self.buffers:
            if self.stop_count != self.picamera2.stop_count:
                for _, buffer in self.buffers.items():
                    glDeleteTextures(1, [buffer.texture])
                self.buffers = {}
                self.stop_count = self.picamera2.stop_count
            self.buffers[completed_request.request] = Buffer(self.egl_display, completed_request, self.max_texture_size)

        if self._overlay_dirty and self.overlay_array is not None:
            glBindTexture(GL_TEXTURE_2D, self.overlay_texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            height, width, _ = self.overlay_array.shape
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, self.overlay_array)
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

    def set_overlay(self, overlay):
        with self.lock:
            self.overlay_array = overlay
            self.overlay_present = overlay is not None
            self._overlay_dirty = overlay is not None
        self.update()


def str_to_fourcc(str):
    assert len(str) == 4
    fourcc = 0
    for i, v in enumerate([ord(c) for c in str]):
        fourcc |= v << (i * 8)
    return fourcc


def get_gl_extensions():
    n = GLint()
    glGetIntegerv(GL_NUM_EXTENSIONS, n)
    gl_extensions = []
    for i in range(n.value):
        gl_extensions.append(gl.glGetStringi(GL_EXTENSIONS, i).decode())
    return gl_extensions


def check_gl_extensions(required_extensions):
    extensions = get_gl_extensions()

    if False:
        print("GL EXTENSIONS: ", " ".join(extensions))

    for ext in required_extensions:
        if ext not in extensions:
            raise Exception(ext + " missing")


def get_egl_extensions(egl_display):
    return eglQueryString(egl_display, EGL_EXTENSIONS).decode().split(" ")


def check_egl_extensions(egl_display, required_extensions):
    extensions = get_egl_extensions(egl_display)

    if False:
        print("EGL EXTENSIONS: ", " ".join(extensions))

    for ext in required_extensions:
        if ext not in extensions:
            raise Exception(ext + " missing")


class Buffer:
    """DMA-buf → EGLImage → external-OES texture.  Created once per camera buffer."""

    # libcamera format string -> DRM fourcc; 24-bit formats are not supported
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
            raise RuntimeError(f"Format {pixel_format} not supported by GL preview")
        fmt = str_to_fourcc(self.FMT_MAP[pixel_format])
        w, h = (cfg.size.width, cfg.size.height)
        if w > max_texture_size or h > max_texture_size:
            raise RuntimeError(f"Maximum supported preview image size is {max_texture_size}")
        if pixel_format in ("YUV420", "YVU420"):
            h2 = h // 2
            stride2 = cfg.stride // 2
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
                EGL_WIDTH, w,
                EGL_HEIGHT, h,
                EGL_LINUX_DRM_FOURCC_EXT, fmt,
                EGL_DMA_BUF_PLANE0_FD_EXT, fb.planes[0].fd,
                EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                EGL_DMA_BUF_PLANE0_PITCH_EXT, cfg.stride,
                EGL_NONE,
            ]
            # fmt: on

        image = eglCreateImageKHR(display, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, None, attribs)

        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_EXTERNAL_OES, self.texture)
        glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glEGLImageTargetTexture2DOES(GL_TEXTURE_EXTERNAL_OES, image)

        eglDestroyImageKHR(display, image)
