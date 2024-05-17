from libcamera import Rectangle, Size
import os
import numpy as np

network_firmware_symlink = "/lib/firmware/imx500_network.fpk"

def input_tensor_image(input_tensor, input_tensor_size, norm_val, norm_shift,
                       div_val=1, div_shift=(0, 0, 0, 0)):
    """Convert input tensor in planar format to interleaved RGB."""
    r1 = np.array(input_tensor, dtype=np.uint8).astype(np.int16).reshape((3, ) + input_tensor_size)
    r1 = r1[(2, 1, 0), :, :]
    for i in [0, 1, 2]:
        delta = norm_val[i] if ((norm_val[i] >> 8) & 1) == 0 else -((~norm_val[i] + 1) & 0x1ff)
        r1[i] = ((((r1[i] << norm_shift[i]) - delta) << div_shift[i]) // div_val) & 0xff

    return np.transpose(r1, (1, 2, 0)).astype(np.uint8)


def convert_inference_coords(coords: list, full_sensor_resolution: Rectangle, scaler_crop: Rectangle,
                             isp_output_size: Size, sensor_output_size: Size):
    """Convert relative inference coordinates into the output image coordinates space."""
    sensor_crop = scaler_crop.scaled_by(sensor_output_size, full_sensor_resolution.size)
    y0, x0, y1, x1 = coords
    width = full_sensor_resolution.size.width
    height = full_sensor_resolution.size.height
    obj = Rectangle(
        *np.maximum(
            np.array([x0 * width, y0 * height, (x1 - x0) * width, (y1 - y0) * height]),
            0,
        ).astype(np.int32)
    )
    obj_sensor = obj.scaled_by(sensor_output_size, Size(width, height))
    obj_bound = obj_sensor.bounded_to(sensor_crop)
    obj_translated = obj_bound.translated_by(-sensor_crop.topLeft)
    obj_scaled = obj_translated.scaled_by(isp_output_size, sensor_crop.size)

    return obj_scaled


def set_network_firmware(firmware_filename):
    """
    Provides a firmware fpk file to upload to the IMX500. This must be called before Picamera2 is instantiation.
    network_firmware_symlink points to another symlink (e.g. /home/pi/imx500_network_firmware/imx500_network.fpk)
    accessable by the user. This accessable symlink needs to point to the network fpk file that will eventually
    be pushed into the IMX500 by the kernel driver.
    """

    if not os.path.isfile(firmware_filename):
        raise RuntimeError("Firmware file " + firmware_filename + " does not exist.")

    # Check if network_firmware_symlink points to another symlink.
    if not os.path.islink(network_firmware_symlink) or \
       not os.path.islink(os.readlink(network_firmware_symlink)):
        print(f"{network_firmware_symlink} is not a symlink, or its target is not a symlink, "
               "ignoring custom network firmware file.")
        return

    # Update the user accessable symlink to the user requested firmware if needed.
    local_symlink = os.readlink(network_firmware_symlink)
    if not os.path.samefile(os.readlink(local_symlink), firmware_filename):
        os.remove(local_symlink)
        os.symlink(firmware_filename, local_symlink)
