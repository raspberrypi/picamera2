import fcntl
import os

from v4l2 import VIDIOC_S_CTRL, v4l2_control

from picamera2 import Picamera2

HDR_CTRL_ID = 0x009a0915


class IMX708:
    def __init__(self, camera_num=None):
        self.device_fd = None

        camera_info = Picamera2.global_camera_info()
        if camera_num is None:
            camera_id = next((c['Id'] for c in camera_info if c['Model'] == 'imx708'), None)
        else:
            camera_id = next((c['Id'] for c in camera_info if c['Num'] == camera_num), None)

        if camera_id is None:
            raise RuntimeError('IMX708: Requested IMX708 camera device not be found')

        for i in range(16):
            test_dir = f'/sys/class/video4linux/v4l-subdev{i}/device'
            module_dir = f'{test_dir}/driver/module'
            id_dir = f'{test_dir}/of_node'
            if os.path.exists(module_dir) and os.path.islink(module_dir) and 'imx708' in os.readlink(module_dir):
                if os.path.islink(id_dir) and camera_id in os.readlink(id_dir):
                    self.device_fd = open(f'/dev/v4l-subdev{i}', 'rb+', buffering=0)
                    break

        if self.device_fd is None:
            raise RuntimeError('IMX708: Requested camera v4l2 device node not found')

    def __del__(self):
        self.close()

    def close(self):
        if self.device_fd:
            self.device_fd.close()
            self.device_fd = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def set_sensor_hdr_mode(self, enable: bool):
        """
        Set the sensor HDR mode (True/False) on the IMX708 device.

        Note that after changing the HDR mode, you must
        re-initialise the Picamera2 object to cache the updated sensor modes.
        """
        ctrl = v4l2_control()
        ctrl.id = HDR_CTRL_ID
        ctrl.value = int(enable)

        try:
            fcntl.ioctl(self.device_fd, VIDIOC_S_CTRL, ctrl)
        except OSError as err:
            print(f'IMX708: Unable to set HDR control in the device node: {err}')

        # Must reset the camera manager so that cached sensor modes can be refreshed.
        Picamera2._cm.reset()
