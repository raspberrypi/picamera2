from picamera2.configuration import *

cm = libcamera.CameraManager.singleton()
camera = cm.cameras[0]
acq = camera.acquire()

def main():
    main = {"role": STILL,
            "size": (1280, 720),
            'buffer_count': 3,
            'pixel_format': 'BGR888',
            'color_space': COLORSPACE_JPEG}

    lores = {"role": VIEWFINDER,
             "size": (640, 480),
             'buffer_count': 3,
             'pixel_format': 'YUV420'}

    transform = {'hflip': 1, 'vflip': 1}

    options = CameraOptions(main=main, lores=lores, transform=transform)
    print(options.config)

    cfg = build_libcamera_config(options)
    valid = validate_libcamera_config(cfg)

    if valid:
        is_configured = configure_libcamera(cfg)
        if is_configured:
            print("Libcamera is configured!")



def build_libcamera_config(CameraOptions):
    opts = CameraOptions
    all_streams = [opts.main, opts.lores, opts.raw]
    user_defined_streams = [s for s in all_streams if s.role is not None]
    roles = [stream.role for stream in user_defined_streams]
    libcamera_config = camera.generate_configuration(roles)
    for stream in user_defined_streams:
        _idx = user_defined_streams.index(stream)
        for key, val in stream._libcamera_options.items():
            setattr(libcamera_config.at(_idx), key, val)
    libcamera_config.transform = libcamera.Transform(**opts.transform._libcamera_options)
    return libcamera_config

def validate_libcamera_config(libcamera_config):
    VALID_CONFIG = libcamera.CameraConfiguration.Status.Valid
    INVALID_CONFIG = libcamera.CameraConfiguration.Status.Invalid
    ADJUSTED_CONFIG = libcamera.CameraConfiguration.Status.Adjusted
    status = libcamera_config.validate()
    if status == VALID_CONFIG:
        return True
    elif status == INVALID_CONFIG:
        raise RuntimeError("An invalid libcamera config was supplied.")
    elif status == ADJUSTED_CONFIG:
        print("Libcamera config was adjusted.")
        return True

def configure_libcamera(libcamera_config):
    if camera.configure(libcamera_config) >= 0:
        return True
    else:
        return False

if __name__ == "__main__":
    main()
