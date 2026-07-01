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
