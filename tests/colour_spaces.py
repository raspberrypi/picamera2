from libcamera import ColorSpace

import picamera2.formats as formats
from picamera2 import Picamera2

picam2 = Picamera2()


def configure_and_check(config):
    check_colour_space = ColorSpace(config["colour_space"])
    picam2.configure(config)
    config = picam2.camera_config

    if config["colour_space"] == check_colour_space:
        print("Headline colour space matches", check_colour_space)
    else:
        print("ERROR: headline colour space changed from", check_colour_space, "to", config["colour_space"])
        quit()

    check_main_colour_space = ColorSpace(check_colour_space)
    if formats.is_RGB(config["main"]["format"]):
        check_main_colour_space.ycbcrEncoding = ColorSpace.YcbcrEncoding.Null
        check_main_colour_space.range = ColorSpace.Range.Full

    libcamera_config = picam2.libcamera_config

    if libcamera_config.at(picam2.main_index).color_space == check_main_colour_space:
        print("Main stream colour spaces match", check_main_colour_space)
    else:
        print("ERROR: main stream colour space is", libcamera_config.at(picam2.main_index).color_space,
              "expected", check_main_colour_space)
        quit()

    if picam2.lores_index >= 0:
        if libcamera_config.at(picam2.lores_index).color_space == check_colour_space:
            print("Lores stream colour spaces match", check_colour_space)
        else:
            print("ERROR: lores stream colour space is", libcamera_config.at(picam2.lores_index).color_space,
                  "expected", check_colour_space)
            quit()

    if picam2.raw_index >= 0:
        if libcamera_config.at(picam2.raw_index).color_space == ColorSpace.Raw():
            print("Raw stream colour spaces match", ColorSpace.Raw())
        else:
            print("ERROR: raw stream colour space is", libcamera_config.at(picam2.raw_index).color_space,
                  "expected", ColorSpace.Raw())
            quit()


for colour_space in (ColorSpace.Sycc(), ColorSpace.Smpte170m(), ColorSpace.Rec709()):

    for format in ("RGB888", "YUV420"):
        print("Checking with colour space", colour_space, "and format", format)

        print("Main only")
        config = picam2.create_preview_configuration({"format": format}, colour_space=colour_space)
        configure_and_check(config)

        print("Main and lores", flush=True)
        config = picam2.create_preview_configuration({"format": format}, lores={}, colour_space=colour_space)
        configure_and_check(config)

        print("Main and raw", flush=True)
        config = picam2.create_preview_configuration({"format": format}, raw={}, colour_space=colour_space)
        configure_and_check(config)

        print("Main, lores and raw", flush=True)
        config = picam2.create_preview_configuration({"format": format}, lores={}, raw={}, colour_space=colour_space)
        configure_and_check(config)
