from libcamera import Rectangle, Size
import numpy as np


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
    obj = Rectangle(*np.maximum(np.array([x0, y0, x1 - x0, y1 - y0]) * 1000, 0).astype(np.int32))
    obj_sensor = obj.scaled_by(sensor_output_size, Size(1000, 1000))
    obj_bound = obj_sensor.bounded_to(sensor_crop)
    obj_translated = obj_bound.translated_by(-sensor_crop.topLeft)
    obj_scaled = obj_translated.scaled_by(isp_output_size, sensor_output_size)

    return obj_scaled
