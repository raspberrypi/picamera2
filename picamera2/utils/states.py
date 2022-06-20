import libcamera

class LibcameraConfigStatus:
    VALID = libcamera.CameraConfiguration.Status.Valid
    INVALID = libcamera.CameraConfiguration.Status.Invalid
    ADJUSTED = libcamera.CameraConfiguration.Status.Adjusted

class Role:
    STILL = libcamera.StreamRole.StillCapture
    RAW = libcamera.StreamRole.Raw
    VIDEO = libcamera.StreamRole.VideoRecording
    VIEWFINDER = libcamera.StreamRole.Viewfinder
