import ctypes
import fcntl
import io
import json
import multiprocessing
import os
import struct
import sys
import time
from typing import List, Optional

import jsonschema
import numpy as np
from libarchive.read import fd_reader
from libcamera import Rectangle, Size
from tqdm import tqdm
from v4l2 import (VIDIOC_S_CTRL, VIDIOC_S_EXT_CTRLS, v4l2_control,
                  v4l2_ext_control, v4l2_ext_controls)

from picamera2 import CompletedRequest, Picamera2

NETWORK_NAME_LEN = 64
MAX_NUM_TENSORS = 16
MAX_NUM_DIMENSIONS = 16

FW_LOADER_STAGE = 0
FW_MAIN_STAGE = 1
FW_NETWORK_STAGE = 2

NETWORK_FW_FD_CTRL_ID = 0x00982901
ROI_CTRL_ID = 0x00982900


# struct OutputTensorInfo from libcamera
class OutputTensorInfo(ctypes.LittleEndianStructure):
    _fields_ = [
        ('tensor_data_num', ctypes.c_uint32),
        ('num_dimensions', ctypes.c_uint32),
        ('size', ctypes.c_uint16 * MAX_NUM_DIMENSIONS),
    ]


# struct CnnOutputTensorInfoExported from libcamera
class CnnOutputTensorInfoExported(ctypes.LittleEndianStructure):
    _fields_ = [
        ('network_name', ctypes.c_char * NETWORK_NAME_LEN),
        ('num_tensors', ctypes.c_uint32),
        ('info', OutputTensorInfo * MAX_NUM_TENSORS)
    ]


class NetworkIntrinsics:
    def __init__(self, val=None):
        self.__intrinsics: Optional[dict] = None
        self.__schema = {
            "$schema": "https://json-schema.org/draft-07/schema",
            "title": "network_intrinsics",
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "enum": ["classification", "object detection", "pose estimation", "segmentation"],
                    "description": "Network task",
                },
                "inference_rate": {"type": "number", "minimum": 0},
                "cpu": {
                    "type": "object",
                    "properties": {
                        "bbox_normalization": {"type": "boolean"},
                        "bbox_order": {"type": "string", "enum": ["xy", "yx"]},
                        "softmax": {"type": "boolean"},
                        "post_processing": {"type": "string"},
                    },
                },
                "input_aspect_ratio": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer", "exclusiveMinimum": 0},
                        "height": {"type": "integer", "exclusiveMinimum": 0},
                    },
                    "required": ["width", "height"],
                },
                "classes": {
                    "type": "object",
                    "properties": {
                        "labels": {"type": "array", "items": {"type": "string"}},
                        "ignore_undefined": {"type": "boolean"},
                    },
                },
            },
        }
        if val is not None:
            jsonschema.validate(val, self.__schema)
            self.__intrinsics = val

        self.__defaults = {'inference_rate': 30.0}
        jsonschema.validate(self.__defaults, self.__schema | {'additionalProperties': False})

    @property
    def intrinsics(self) -> Optional[dict]:
        return self.__intrinsics

    @intrinsics.setter
    def intrinsics(self, val):
        jsonschema.validate(val, self.__schema)
        self.__intrinsics = val

    def __repr__(self):
        return json.dumps(self.__intrinsics) if self.__intrinsics else ""

    def __top_level_validated_insert(self, val: dict):
        jsonschema.validate(val, self.__schema | {'additionalProperties': False})
        self.__intrinsics = self.__intrinsics | val if self.__intrinsics else val

    def __intrinsics_has_key(self, key: str) -> bool:
        return key in self.__intrinsics if self.__intrinsics else False

    def __intrinsics_get_key(self, key, default=None):
        return self.__intrinsics.get(key, default) if self.__intrinsics else default

    def update_with_defaults(self):
        # Updates intrinsics with default settings (but does not overwrite)
        if not self.__intrinsics:
            self.__intrinsics = {}
        self.__intrinsics = self.__defaults | self.__intrinsics

    @property
    def task(self) -> Optional[str]:
        return self.__intrinsics_get_key('task')

    @task.setter
    def task(self, val: str):
        self.__top_level_validated_insert({'task': val})

    @property
    def inference_rate(self) -> Optional[float]:
        return self.__intrinsics_get_key('inference_rate')

    @inference_rate.setter
    def inference_rate(self, val: float):
        if val < 0:
            if self.__intrinsics is not None:
                self.__intrinsics.pop('inference_rate', None)
        else:
            self.__top_level_validated_insert({'inference_rate': val})

    @property
    def fps(self) -> Optional[float]:
        # @deprecated("Prefer inference_rate")
        return self.inference_rate

    @fps.setter
    def fps(self, val: Optional[float]):
        # @deprecated("Prefer inference_rate")
        self.inference_rate = val

    def __get_cpu(self, key: str):
        return self.__intrinsics['cpu'].get(key, None) if self.__intrinsics_has_key('cpu') else None

    def __set_cpu(self, val: dict):
        jsonschema.validate({'cpu': val}, self.__schema | {'additionalProperties': False})
        cpu = self.__intrinsics_get_key('cpu', {}) | val
        if self.__intrinsics:
            self.__intrinsics['cpu'] = cpu
        else:
            self.__intrinsics = {'cpu': cpu}

    @property
    def bbox_normalization(self) -> Optional[bool]:
        return self.__get_cpu('bbox_normalization')

    @bbox_normalization.setter
    def bbox_normalization(self, val: Optional[bool]):
        if val is None:
            return

        if val:
            self.__set_cpu({'bbox_normalization': val})
        elif self.__intrinsics_has_key('cpu'):
            self.__intrinsics['cpu'].pop('bbox_normalization', None)

        if self.__intrinsics_has_key('cpu') and len(self.__intrinsics['cpu']) == 0:
            self.__intrinsics.pop('cpu')

    @property
    def bbox_order(self) -> Optional[str]:
        return self.__get_cpu('bbox_order')

    @bbox_order.setter
    def bbox_order(self, val: str):
        if val not in ["xy", "yx"]:
            raise ValueError("bbox_order must be either 'xy' or 'yx'")
        self.__set_cpu({'bbox_order': val})
        if self.__intrinsics_has_key('cpu') and len(self.__intrinsics['cpu']) == 0:
            self.__intrinsics.pop('cpu')

    @property
    def softmax(self) -> Optional[bool]:
        return self.__get_cpu('softmax')

    @softmax.setter
    def softmax(self, val: Optional[bool]):
        if val is None:
            return

        if val:
            self.__set_cpu({'softmax': val})
        elif self.__intrinsics_has_key('cpu'):
            self.__intrinsics['cpu'].pop('softmax', None)

        if self.__intrinsics_has_key('cpu') and len(self.__intrinsics['cpu']) == 0:
            self.__intrinsics.pop('cpu')

    @property
    def postprocess(self) -> Optional[str]:
        return self.__get_cpu('post_processing')

    @postprocess.setter
    def postprocess(self, val: str):
        if val != "":
            self.__set_cpu({'post_processing': val})
        elif self.__intrinsics_has_key('cpu'):
            self.__intrinsics['cpu'].pop('post_processing', None)

        if self.__intrinsics_has_key('cpu') and len(self.__intrinsics['cpu']) == 0:
            self.__intrinsics.pop('cpu')

    @property
    def preserve_aspect_ratio(self) -> Optional[bool]:
        if not self.__intrinsics_has_key('input_aspect_ratio'):
            return None
        ar = self.__intrinsics['input_aspect_ratio']
        return ar['width'] == ar['height']

    @preserve_aspect_ratio.setter
    def preserve_aspect_ratio(self, val: Optional[bool]):
        if val is None:
            return

        if val:
            iar = {'input_aspect_ratio': {'width': 1, 'height': 1}}
            self.__top_level_validated_insert(iar)
        elif self.__intrinsics_has_key('input_aspect_ratio'):
            self.__intrinsics.pop('input_aspect_ratio')

    @property
    def labels(self) -> Optional[List[str]]:
        return self.__intrinsics['classes'].get('labels', None) if self.__intrinsics_has_key('classes') else None

    @labels.setter
    def labels(self, val: List[str]):
        if len(val) != 0:
            classes = {'labels': val}
            jsonschema.validate({'classes': classes}, self.__schema | {'additionalProperties': False})

            classes = self.__intrinsics_get_key('classes', {}) | classes
            if self.__intrinsics:
                self.__intrinsics['classes'] = classes
            else:
                self.__intrinsics = {'classes': classes}
        elif self.__intrinsics_has_key('classes'):
            self.__intrinsics['classes'].pop('labels', None)
            if len(self.__intrinsics['classes']) == 0:
                self.__intrinsics.pop('classes')

    @property
    def ignore_dash_labels(self) -> Optional[bool]:
        return self.__intrinsics['classes'].get('ignore_undefined', None) if self.__intrinsics_has_key('classes') else None

    @ignore_dash_labels.setter
    def ignore_dash_labels(self, val: Optional[bool]):
        if val is None:
            return

        if val:
            iu = {'ignore_undefined': val}
            jsonschema.validate({'classes': iu}, self.__schema | {'additionalProperties': False})

            classes = {'classes': self.__intrinsics_get_key('classes', {}) | iu}
            self.__intrinsics = self.__intrinsics | classes if self.__intrinsics else classes
        elif self.__intrinsics_has_key('classes'):
            self.__intrinsics['classes'].pop('ignore_undefined', None)
            if len(self.__intrinsics['classes']) == 0:
                self.__intrinsics.pop('classes')


class IMX500:
    def __init__(self, network_file: str, camera_id: str = ''):
        self.device_fd = None
        self.fw_progress = None
        self.fw_progress_chunk = None
        self.__cfg = {'network_file': network_file, 'input_tensor': {}}

        imx500_device_id = None
        spi_device_id = None
        for i in range(32):
            test_dir = f'/sys/class/video4linux/v4l-subdev{i}/device'
            module_dir = f'{test_dir}/driver/module'
            id_dir = f'{test_dir}/of_node'
            if os.path.exists(module_dir) and os.path.islink(module_dir) and os.path.islink(id_dir) \
                    and 'imx500' in os.readlink(module_dir):
                if camera_id == '' or (camera_id in os.readlink(id_dir)):
                    self.device_fd = open(f'/dev/v4l-subdev{i}', 'rb+', buffering=0)
                    imx500_device_id = os.readlink(test_dir).split('/')[-1]
                    spi_device_id = imx500_device_id.replace('001a', '0040')
                    camera_info = Picamera2.global_camera_info()
                    self.__camera_num = next((c['Num'] for c in camera_info if c['Model'] == 'imx500'
                                              and c['Id'] in os.readlink(id_dir)))
                    break

        if self.device_fd is None:
            raise RuntimeError('IMX500: Requested camera dev-node not found')

        # Progress status specific debugfs entries.
        if imx500_device_id:
            self.fw_progress = open(f'/sys/kernel/debug/imx500-fw:{imx500_device_id}/fw_progress', 'r')
        if spi_device_id:
            self.fw_progress_chunk = open(f'/sys/kernel/debug/rp2040-spi:{spi_device_id}/transfer_progress', 'r')

        if self.config['network_file'] != '':
            self.__set_network_firmware(os.path.abspath(self.config['network_file']))
            self.__ni_from_network(os.path.abspath(self.config['network_file']))

        if 'norm_val' not in self.__cfg['input_tensor']:
            self.__cfg['input_tensor']['norm_val'] = [-2048, -2048, -2048]
        if 'norm_shift' not in self.__cfg:
            self.__cfg['input_tensor']['norm_shift'] = [4, 4, 4]
        if 'div_val' not in self.__cfg:
            self.__cfg['input_tensor']['div_val'] = [1024, 1024, 1024]
        if 'div_shift' not in self.__cfg:
            self.__cfg['input_tensor']['div_shift'] = 6

        full_sensor = self.__get_full_sensor_resolution()
        self.set_inference_roi_abs(full_sensor.to_tuple())

    @staticmethod
    def __get_full_sensor_resolution():
        """Full sensor resolution as a Rectangle object."""
        return Rectangle(0, 0, 4056, 3040)

    def __del__(self):
        if self.device_fd:
            self.device_fd.close()

    @property
    def camera_num(self):
        return self.__camera_num

    @property
    def config(self) -> dict:
        return self.__cfg

    @property
    def network_intrinsics(self) -> Optional[NetworkIntrinsics]:
        return self.__cfg.get('intrinsics', None)

    def convert_inference_coords(self, coords: tuple, metadata: dict, picam2: Picamera2, stream='main') -> tuple:
        """Convert relative inference coordinates into the output image coordinates space."""
        isp_output_size = Size(*picam2.camera_configuration()[stream]['size'])
        sensor_output_size = Size(*picam2.camera_configuration()['raw']['size'])
        scaler_crop = Rectangle(*metadata['ScalerCrop'])

        y0, x0, y1, x1 = coords
        full_sensor = self.__get_full_sensor_resolution()
        width, height = full_sensor.size.to_tuple()
        obj = Rectangle(
            *np.maximum(
                np.array([x0 * width, y0 * height, (x1 - x0) * width, (y1 - y0) * height]),
                0,
            ).astype(np.int32)
        )
        out = self.__get_obj_scaled(obj, isp_output_size, scaler_crop, sensor_output_size)
        return out.to_tuple()

    def get_fw_upload_progress(self, stage_req) -> tuple:
        """Returns the current progress of the fw upload in the form of (current, total)."""
        progress_block = 0
        progress_chunk = 0
        size = 0
        stage = 0

        if self.fw_progress:
            self.fw_progress.seek(0)
            progress = self.fw_progress.readline().strip().split()
            stage = int(progress[0])
            progress_block = int(progress[1])
            size = int(progress[2])

        if self.fw_progress_chunk:
            self.fw_progress_chunk.seek(0)
            progress_chunk = int(self.fw_progress_chunk.readline().strip())

        if stage == stage_req:
            return (min(progress_block + progress_chunk, size), size)
        else:
            return (0, 0)

    def show_network_fw_progress_bar(self):
        p = multiprocessing.Process(target=self.__do_progress_bar,
                                    args=(FW_NETWORK_STAGE, 'Network Firmware Upload'))
        p.start()
        p.join(0)

    def __do_progress_bar(self, stage_req, title):
        with tqdm(unit='bytes', unit_scale=True, unit_divisor=1024, desc=title, leave=True) as t:
            last_update = 0
            while True:
                current, total = self.get_fw_upload_progress(stage_req)
                if total:
                    t.total = total
                    t.update(current - last_update)
                    last_update = current
                    if current > 0.95 * total:
                        t.update(total - last_update)
                        break
                time.sleep(0.5)

    def get_roi_scaled(self, request: CompletedRequest, stream="main") -> tuple:
        """Get the region of interest (ROI) in output image coordinates space."""
        picam2 = request.picam2
        isp_output_size = self.get_isp_output_size(picam2, stream)
        sensor_output_size = self.get_isp_output_size(picam2, 'raw')
        scaler_crop = Rectangle(*request.get_metadata()['ScalerCrop'])
        obj = self.__get_full_sensor_resolution()
        roi = self.__get_obj_scaled(obj, isp_output_size, scaler_crop, sensor_output_size)
        return roi.to_tuple()

    @staticmethod
    def get_isp_output_size(picam2, stream="main") -> tuple:
        return Size(*picam2.camera_configuration()[stream]['size'])

    def __get_obj_scaled(self, obj, isp_output_size, scaler_crop, sensor_output_size) -> Rectangle:
        """Scale the object coordinates based on the camera configuration and sensor properties."""
        full_sensor = self.__get_full_sensor_resolution()
        width, height = full_sensor.size.to_tuple()
        sensor_crop = scaler_crop.scaled_by(sensor_output_size, full_sensor.size)

        # Make sure the object is bound to the user requested ROI.
        if 'roi' in self.config and self.config['roi'] != Rectangle(0, 0, 0, 0):
            obj = obj.bounded_to(self.config['roi'])

        obj_sensor = obj.scaled_by(sensor_output_size, Size(width, height))
        obj_bound = obj_sensor.bounded_to(sensor_crop)
        obj_translated = obj_bound.translated_by(-sensor_crop.topLeft)
        obj_scaled = obj_translated.scaled_by(isp_output_size, sensor_crop.size)
        return obj_scaled

    def get_input_size(self) -> tuple:
        """Get the model input tensor size as (width, height)."""
        return self.config['input_tensor_size']

    def input_tensor_image(self, input_tensor):
        """Convert input tensor in planar format to interleaved RGB."""
        width = self.config['input_tensor']['width']
        height = self.config['input_tensor']['height']
        r1 = np.array(input_tensor, dtype=np.uint8).astype(np.int32).reshape((3,) + (height, width))
        r1 = r1[(2, 1, 0), :, :]
        norm_val = self.config['input_tensor']['norm_val']
        norm_shift = self.config['input_tensor']['norm_shift']
        div_val = self.config['input_tensor']['div_val']
        div_shift = self.config['input_tensor']['div_shift']
        for i in [0, 1, 2]:
            r1[i] = ((((r1[i] << norm_shift[i]) - norm_val[i]) << div_shift) // div_val[i]) & 0xff

        return np.transpose(r1, (1, 2, 0)).astype(np.uint8)

    def get_outputs(self, metadata: dict, add_batch=False) -> Optional[list[np.ndarray]]:
        """Get the model outputs."""
        output_tensor = metadata.get('CnnOutputTensor')
        if not output_tensor:
            return None

        np_output = np.fromiter(output_tensor, dtype=np.float32)
        output_shapes = self.get_output_shapes(metadata)
        offset = 0
        outputs = []
        for tensor_shape in output_shapes:
            size = np.prod(tensor_shape)
            reshaped_tensor = np_output[offset:offset + size].reshape(tensor_shape, order='F')
            if add_batch:
                reshaped_tensor = np.expand_dims(reshaped_tensor, 0)
            outputs.append(reshaped_tensor)
            offset += size
        return outputs

    def get_output_shapes(self, metadata: dict) -> list[tuple[int]]:
        """Get the model output shapes if no output return empty list."""
        output_tensor_info = metadata.get('CnnOutputTensorInfo')
        if not output_tensor_info:
            return []
        output_tensor_info = self.__get_output_tensor_info(output_tensor_info)['info']
        return [o['size'] for o in output_tensor_info]

    def set_inference_roi_abs(self, roi: tuple):
        """
        Set the absolute inference image crop.

        Specify an absolute region of interest in the form a (left, top, width, height) crop for the input inference
        image. The co-ordinates are based on the full sensor resolution.
        """
        roi = Rectangle(*roi)
        roi = roi.bounded_to(self.__get_full_sensor_resolution())

        r = (ctypes.c_uint32 * 4)()
        r[0] = roi.x
        r[1] = roi.y
        r[2] = roi.width
        r[3] = roi.height

        c = (v4l2_ext_control * 1)()
        c[0].p_u32 = r
        c[0].id = ROI_CTRL_ID
        c[0].size = 16

        ctrl = v4l2_ext_controls()
        ctrl.count = 1
        ctrl.controls = c

        try:
            fcntl.ioctl(self.device_fd, VIDIOC_S_EXT_CTRLS, ctrl)
            self.__cfg['roi'] = roi
        except OSError as err:
            print(f'IMX500: Unable to set ROI control in the device driver: {err}')

    def set_inference_aspect_ratio(self, aspect_ratio: tuple):
        """
        Set the aspect ratio of the inference image.

        Specify a pixel aspect ratio needed for the input inference image relative to the full sensor resolution.
        This simply calculates an ROI based on a centre crop and calls set_inference_roi_abs().
        """
        f = self.__get_full_sensor_resolution()
        r = f.size.bounded_to_aspect_ratio(Size(aspect_ratio[0], aspect_ratio[1]))
        r = r.centered_to(f.center).enclosed_in(f)
        self.set_inference_roi_abs(r.to_tuple())

    def set_auto_aspect_ratio(self):
        """Set the inference image crop to presereve the input tensor aspect ratio."""
        self.set_inference_aspect_ratio(self.config['input_tensor_size'])

    def __get_output_tensor_info(self, tensor_info) -> dict:
        """Return the network string along with a list of output tensor parameters."""
        if type(tensor_info) not in [bytes, bytearray]:
            tensor_info = bytes(tensor_info)

        size = ctypes.sizeof(CnnOutputTensorInfoExported)
        if len(tensor_info) != size:
            raise ValueError(f'tensor info length {len(tensor_info)} does not match expected size {size}')

        # Create an instance of the struct and copy data into it
        parsed = CnnOutputTensorInfoExported()
        ctypes.memmove(ctypes.addressof(parsed), tensor_info, size)

        result = {
            'network_name': parsed.network_name.decode('utf-8').strip('\x00'),
            'num_tensors': parsed.num_tensors,
            'info': []
        }

        for t in parsed.info[0:parsed.num_tensors]:
            info = {
                'tensor_data_num': t.tensor_data_num,
                'num_dimensions': t.num_dimensions,
                'size': list(t.size)[0:t.num_dimensions],
            }
            result['info'].append(info)

        return result

    def __get_input_tensor_info(self, tensor_info) -> tuple[str, int, int, int]:
        """Return the input tensor parameters in the form (network_name, width, height, num_channels)."""
        NETWORK_NAME_LEN = 64
        tensor_fmt = f'{NETWORK_NAME_LEN}sIII'

        if type(tensor_info) not in [bytes, bytearray]:
            tensor_info = bytes(tensor_info)

        network_name, width, height, num_channels = struct.unpack(tensor_fmt, tensor_info)
        network_name = network_name.decode('utf-8').rstrip('\0')
        return (network_name, width, height, num_channels)

    @staticmethod
    def get_kpi_info(metadata: dict) -> Optional[tuple[float, float]]:
        """Return the KPI parameters in the form (dnn_runtime, dsp_runtime) in milliseconds."""
        kpi_info = metadata.get('CnnKpiInfo')
        if kpi_info is None:
            return None
        dnn_runtime, dsp_runtime = kpi_info[0], kpi_info[1]
        return dnn_runtime / 1000, dsp_runtime / 1000

    def __set_network_firmware(self, network_filename: str):
        """Provides a firmware rpk file to upload to the IMX500. This must be called before Picamera2 is configured."""
        if not os.path.isfile(network_filename):
            raise RuntimeError(f'Firmware file {network_filename} does not exist.')

        fd = os.open(network_filename, os.O_RDONLY)
        if fd:
            ctrl = v4l2_control()
            ctrl.id = NETWORK_FW_FD_CTRL_ID
            ctrl.value = fd

            try:
                fcntl.ioctl(self.device_fd, VIDIOC_S_CTRL, ctrl)
                print('\n------------------------------------------------------------------------------------------------------------------\n'  # noqa
                      'NOTE: Loading network firmware onto the IMX500 can take several minutes, please do not close down the application.'  # noqa
                      '\n------------------------------------------------------------------------------------------------------------------\n', file=sys.stderr)  # noqa
            except OSError as err:
                raise RuntimeError(f'IMX500: Unable to set network firmware {network_filename}: {err}')
            finally:
                os.close(fd)

    def __ni_from_network(self, network_filename: str):
        """Extracts 'network_info.txt' from CPIO-archive appended to the network rpk."""
        with open(network_filename, 'rb') as fp:
            fw = memoryview(fp.read())

        # Iterate through network firmware discarding blocks
        cpio_offset = 0
        while True:
            # Parse header (+ current block size)
            (magic, size) = struct.unpack('>4sI', fw[:8])
            if not magic == b'9464':
                break
            fw = fw[size + 60:]
            # Ensure footer is as expected
            (magic,) = struct.unpack('4s', fw[:4])
            if not magic == b'3695':
                raise RuntimeError(f'No matching footer found in firmware file {network_filename}')
            fw = fw[4:]
            cpio_offset += size + 64

        cpio_fd = os.open(network_filename, os.O_RDONLY)
        os.lseek(cpio_fd, cpio_offset, os.SEEK_SET)

        with fd_reader(cpio_fd) as archive:
            for entry in archive:
                if 'network_info.txt' == str(entry):
                    self.__cfg['network_info_raw'] = b''.join(entry.get_blocks())
                elif 'network_intrinsics' == str(entry):
                    self.__cfg['intrinsics'] = NetworkIntrinsics(json.loads(b''.join(entry.get_blocks())))

        os.close(cpio_fd)

        if 'network_info_raw' not in self.__cfg:
            return

        res = {}
        buf = io.StringIO(self.__cfg['network_info_raw'].decode('ascii'))
        for line in buf:
            key, value = line.strip().split('=')
            if key == 'networkID':
                nid: int = 0
                for idx, x in enumerate(value):
                    nid |= (ord(x) - ord('0')) << (20 - idx * 4)
                res[key] = nid
            if key == 'apParamSize':
                res[key] = int(value)
            if key == 'networkNum':
                res[key] = int(value)

        res['network'] = {}
        networks = self.__cfg['network_info_raw'].decode('ascii').split('networkOrdinal=')[1:]
        for nw in networks:
            buf = io.StringIO(nw)
            nw_idx = int(buf.readline())
            nw_properties = {}
            for line in buf:
                key, value = line.strip().split('=')
                nw_properties[key] = value
            res['network'][nw_idx] = nw_properties

        if len(res['network']) != res['networkNum']:
            raise RuntimeError('Insufficient networkNum settings in network_info.txt')

        self.__cfg['network_info'] = res

        # Extract some input tensor config params
        self.__cfg['input_tensor']['width'] = int(res['network'][0]['inputTensorWidth'])
        self.__cfg['input_tensor']['height'] = int(res['network'][0]['inputTensorHeight'])
        self.__cfg['input_tensor_size'] = (self.config['input_tensor']['width'],
                                           self.config['input_tensor']['height'])

        input_format = self.__cfg['network_info']['network'][0]['inputTensorFormat']
        inputTensorNorm_K03 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K03'], 0)
        inputTensorNorm_K13 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K13'], 0)
        inputTensorNorm_K23 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K23'], 0)
        inputTensorNorm_K00 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K00'], 0)
        inputTensorNorm_K22 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K22'], 0)
        inputTensorNorm_K02 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K02'], 0)
        inputTensorNorm_K20 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K20'], 0)
        inputTensorNorm_K11 = int(self.__cfg['network_info']['network'][0]['inputTensorNorm_K11'], 0)

        self.__cfg['input_tensor']['input_format'] = input_format

        if input_format == 'RGB' or input_format == 'BGR':
            norm_val_0 = \
                inputTensorNorm_K03 if ((inputTensorNorm_K03 >> 12) & 1) == 0 else -((~inputTensorNorm_K03 + 1) & 0x1fff)
            norm_val_1 = \
                inputTensorNorm_K13 if ((inputTensorNorm_K13 >> 12) & 1) == 0 else -((~inputTensorNorm_K13 + 1) & 0x1fff)
            norm_val_2 = \
                inputTensorNorm_K23 if ((inputTensorNorm_K23 >> 12) & 1) == 0 else -((~inputTensorNorm_K23 + 1) & 0x1fff)
            norm_val = [norm_val_0, norm_val_1, norm_val_2]
            self.__cfg['input_tensor']['norm_val'] = norm_val
            norm_shift = [4, 4, 4]
            self.__cfg['input_tensor']['norm_shift'] = norm_shift
            if input_format == 'RGB':
                div_val_0 = \
                    inputTensorNorm_K00 if ((inputTensorNorm_K00 >> 11) & 1) == 0 else -((~inputTensorNorm_K00 + 1) & 0x0fff)
                div_val_2 =\
                    inputTensorNorm_K22 if ((inputTensorNorm_K22 >> 11) & 1) == 0 else -((~inputTensorNorm_K22 + 1) & 0x0fff)
            else:
                div_val_0 = \
                    inputTensorNorm_K02 if ((inputTensorNorm_K02 >> 11) & 1) == 0 else -((~inputTensorNorm_K02 + 1) & 0x0fff)
                div_val_2 = \
                    inputTensorNorm_K20 if ((inputTensorNorm_K20 >> 11) & 1) == 0 else -((~inputTensorNorm_K20 + 1) & 0x0fff)
            div_val_1 = \
                inputTensorNorm_K11 if ((inputTensorNorm_K11 >> 11) & 1) == 0 else -((~inputTensorNorm_K11 + 1) & 0x0fff)
            self.__cfg['input_tensor']['div_val'] = [div_val_0, div_val_1, div_val_2]
            self.__cfg['input_tensor']['div_shift'] = 6
