import ctypes
import fcntl
import json
import numpy as np
import os
import struct

from libcamera import Rectangle, Size
from v4l2 import *

class ivs:
    def __init__(self, config_file: str = '', network_file: str = ''):

        self.device_fd = 0
        self.__cfg = {}

        for i in range(5):
            test_dir = f'/sys/class/video4linux/v4l-subdev{i}/device/driver/module'
            if os.path.exists(test_dir) and os.path.islink(test_dir):
                if 'imx500' in os.readlink(test_dir):
                    self.device_fd = open(f'/dev/v4l-subdev{i}', 'rb+', buffering=0)
                    break

        if config_file:
            with open(config_file) as f:
                self.__cfg = json.load(f)
        elif network_file and 'network_file' not in self.config:
            self.__cfg['network_file'] = network_file

        if 'input_tensor' in self.__cfg:
            self.__cfg['input_tensor_size'] = (self.config['input_tensor']['width'],
                                               self.config['input_tensor']['height'])
        else:
            self.__cfg['input_tensor'] = {}

        if 'norm_val' not in self.__cfg['input_tensor']:
            self.__cfg['input_tensor']['norm_val'] = [384, 384, 384]
        if 'norm_shift' not in self.__cfg:
            self.__cfg['input_tensor']['norm_shift'] = [0, 0, 0]
        if 'div_val' not in self.__cfg:
            self.__cfg['input_tensor']['div_val'] = 1
        if 'div_shift' not in self.__cfg:
            self.__cfg['input_tensor']['div_shift'] = [0, 0, 0, 0]

        if 'network_file' in self.config:
            self.__set_network_firmware(os.path.abspath(self.config['network_file']))

    @classmethod
    def from_network_file(ivs, network_file: str):
        return ivs(network_file=network_file)

    def __del__(self):

        if self.device_fd != 0:
            self.device_fd.close()

    @property
    def config(self) -> dict:
        return self.__cfg

    def convert_inference_coords(self, coords: tuple, full_sensor_resolution: tuple, scaler_crop: tuple,
                                 isp_output_size: tuple, sensor_output_size: tuple):
        """Convert relative inference coordinates into the output image coordinates space."""

        full_sensor_resolution = Rectangle(Size(*full_sensor_resolution))
        scaler_crop = Rectangle(*scaler_crop)
        isp_output_size = Size(*isp_output_size)
        sensor_output_size = Size(*sensor_output_size)

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

        # Make sure the object is bound to the user requested ROI.
        if 'roi' in self.config and self.config['roi'] != (0, 0, 0, 0):
            obj = obj.bounded_to(Rectangle(*self.config['roi']))

        obj_sensor = obj.scaled_by(sensor_output_size, Size(width, height))
        obj_bound = obj_sensor.bounded_to(sensor_crop)
        obj_translated = obj_bound.translated_by(-sensor_crop.topLeft)
        obj_scaled = obj_translated.scaled_by(isp_output_size, sensor_crop.size)

        return obj_scaled

    def input_tensor_image(self, input_tensor):
        """Convert input tensor in planar format to interleaved RGB."""

        r1 = np.array(input_tensor, dtype=np.uint8).astype(np.int16).reshape((3, ) + self.config['input_tensor_size'])
        r1 = r1[(2, 1, 0), :, :]
        norm_val = self.config['input_tensor']['norm_val']
        norm_shift = self.config['input_tensor']['norm_shift']
        div_val = self.config['input_tensor']['div_val']
        div_shift = self.config['input_tensor']['div_shift']
        for i in [0, 1, 2]:
            delta = norm_val[i] if ((norm_val[i] >> 8) & 1) == 0 else -((~norm_val[i] + 1) & 0x1ff)
            r1[i] = ((((r1[i] << norm_shift[i]) - delta) << div_shift[i]) // div_val) & 0xff

        return np.transpose(r1, (1, 2, 0)).astype(np.uint8)

    def set_inference_roi_abs(self, roi: tuple):
        """
        Specify an absolute region of interest in the form a (left, top, width, height) crop for the input inference
        image. The co-ordinates are based on the full sensor resolution.
        """

        inference_ctrl_id = 0x00981b00

        if self.device_fd == 0:
            return

        self.__cfg['roi'] = roi

        r = (ctypes.c_uint32 * 4)()
        r[0] = roi[0]
        r[1] = roi[1]
        r[2] = roi[2]
        r[3] = roi[3]

        c = (v4l2_ext_control * 1)()
        c[0].p_u32 = r
        c[0].id = inference_ctrl_id
        c[0].size = 16

        ctrl = v4l2_ext_controls()
        ctrl.count = 1
        ctrl.controls = c
        fcntl.ioctl(self.device_fd, VIDIOC_S_EXT_CTRLS, ctrl)

    def set_inference_aspect_ratio(self, aspect_ratio: tuple, full_sensor_resolution: tuple):
        """
        Specify a pixel aspect ratio needed for the input inference image relative to the full sensor resolution.
        This simply calculates an ROI based on a centre crop and calls set_inference_roi_abs().
        """

        s = Size(full_sensor_resolution[0], full_sensor_resolution[1])
        r = s.bounded_to_aspect_ratio(Size(aspect_ratio[0], aspect_ratio[1]))
        r = r.centered_to(Rectangle(s).center).enclosed_in(Rectangle(s))
        self.set_inference_roi_abs((r.x, r.y, r.width, r.height))

    def get_output_tensor_info(self, tensor_info) -> tuple[str, list[dict]]:
        """
        Return the network string along with a list of output tensor parameters.
        """

        network_name_len = 64
        max_num_tensors = 8
        dim_fmt = 'IHBB'

        if type(tensor_info) not in [bytes, bytearray]:
            tensor_info = bytes(tensor_info)

        tensor_fmt = f'{network_name_len}sI{max_num_tensors * dim_fmt}'
        unpacked = struct.unpack(tensor_fmt, tensor_info)

        network_name = unpacked[0].decode('utf-8').rstrip('\0')
        num_tensors = unpacked[1]

        index = 2
        output_tensor_info = []
        for _ in range(num_tensors):
            tensor_data = unpacked[index:index + 4]
            tensor_info = {
                'tensor_data_num': tensor_data[0],
                'size': tensor_data[1],
                'ordinal': tensor_data[2],
                'serialization_index': tensor_data[3]
            }
            output_tensor_info.append(tensor_info)
            index += 4

        return (network_name, output_tensor_info)

    def get_input_tensor_info(self, tensor_info) -> tuple[str, int, int, int]:
        """
        Return the input tensor parameters in the form (network_name, width, height, num_channels)
        """

        network_name_len = 64
        tensor_fmt = f'{network_name_len}sIII'

        if type(tensor_info) not in [bytes, bytearray]:
            tensor_info = bytes(tensor_info)

        network_name, width, height, num_channels = struct.unpack(tensor_fmt, tensor_info)
        network_name = network_name.decode('utf-8').rstrip('\0')

        return (network_name, width, height, num_channels)


    def __set_network_firmware(self, network_filename: str):
        """
        Provides a firmware fpk file to upload to the IMX500. This must be called before Picamera2 is instantiation.
        network_firmware_symlink points to another symlink (e.g. /home/pi/imx500_network_firmware/imx500_network.fpk)
        accessable by the user. This accessable symlink needs to point to the network fpk file that will eventually
        be pushed into the IMX500 by the kernel driver.
        """

        network_firmware_symlink = "/lib/firmware/imx500_network.fpk"

        if not os.path.isfile(network_filename):
            raise RuntimeError("Firmware file " + network_filename + " does not exist.")

        # Check if network_firmware_symlink points to another symlink.
        if not os.path.islink(network_firmware_symlink) or not os.path.islink(os.readlink(network_firmware_symlink)):
            print(f"{network_firmware_symlink} is not a symlink, or its target is not a symlink, "
                  "ignoring custom network firmware file.")
            return

        # Update the user accessable symlink to the user requested firmware if needed.
        local_symlink = os.readlink(network_firmware_symlink)
        if not os.path.samefile(os.readlink(local_symlink), network_filename):
            os.remove(local_symlink)
            os.symlink(network_filename, local_symlink)

        print("\n------------------------------------------------------------------------------------------------------------------\n"
              "NOTE: Loading network firmware onto the IMX500 can take several minutes, please do not close down the application."
              "\n------------------------------------------------------------------------------------------------------------------\n")
