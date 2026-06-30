from ctypes import CFUNCTYPE, POINTER, c_bool, c_char_p, c_int, c_void_p, cdll, pointer, util

from OpenGL import GL as gl
from OpenGL.EGL.VERSION.EGL_1_0 import EGL_EXTENSIONS, EGLNativeDisplayType, eglGetProcAddress, eglQueryString
from OpenGL.GL import shaders as _shaders
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
