import numpy as np

YUV2RGB_JPEG      = np.array([[1.0,   1.0,   1.0  ], [0.0, -0.344, 1.772], [1.402, -0.714, 0.0]]) # noqa
YUV2RGB_SMPTE170M = np.array([[1.164, 1.164, 1.164], [0.0, -0.392, 2.017], [1.596, -0.813, 0.0]]) # noqa
YUV2RGB_REC709    = np.array([[1.164, 1.164, 1.164], [0.0, -0.213, 2.112], [1.793, -0.533, 0.0]]) # noqa


def YUV420_to_RGB(YUV_in, size, matrix=YUV2RGB_JPEG, rb_swap=True, final_width=0):
    """Convert a YUV420 image to an interleaved RGB image of half resolution.

    The size parameter should include padding if there is any, which can be trimmed off
    at the end with the final_width parameter.
    """
    w, h = size
    w2 = w // 2
    h2 = h // 2
    n = w * h
    n2 = n // 2
    n4 = n // 4

    YUV = np.empty((h2, w2, 3), dtype=int)
    YUV[:, :, 0] = YUV_in[:n].reshape(h, w)[0::2, 0::2]
    YUV[:, :, 1] = YUV_in[n:n + n4].reshape(h2, w2) - 128.0
    YUV[:, :, 2] = YUV_in[n + n4:n + n2].reshape(h2, w2) - 128.0

    if rb_swap:
        matrix = matrix[:, [2, 1, 0]]
    RGB = np.dot(YUV, matrix).clip(0, 255).astype(np.uint8)

    if final_width and final_width != w2:
        RGB = RGB[:, :final_width, :]

    return RGB
