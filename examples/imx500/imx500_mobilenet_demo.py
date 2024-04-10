import cv2
import numpy as np
import picamera2.sony_ivs as IVS
from picamera2 import Picamera2, MappedArray
from libcamera import Rectangle, Size

INPUT_TENSOR_SIZE = (300, 300)
MAX_DETECTIONS = 10
with open("/home/pi/rpicam-apps/assets/imx500_mobilenet_ssd_class80.txt", 'r') as f:
    LABELS = f.read().split()
CONF_THRESHOLD = 0.55

class Detection:
    def __init__(self, coords, category, conf, request, stream='main'):
        """Create a Detection object, recording the bounding box, category and confidence. """
        self.category = category
        self.conf = conf
        # Scale the box to the output stream dimensions.
        isp_output_size = Size(*request.picam2.camera_configuration()[stream]['size'])
        sensor_output_size = Size(*request.picam2.camera_configuration()['raw']['size'])
        full_sensor_resolution = Rectangle(*request.picam2.camera_properties['ScalerCropMaximum'])
        scaler_crop = Rectangle(*request.get_metadata()['ScalerCrop'])
        obj_scaled = IVS.convert_inference_coords(coords, full_sensor_resolution, scaler_crop, isp_output_size,
                                                  sensor_output_size)
        self.box = (obj_scaled.x, obj_scaled.y, obj_scaled.width, obj_scaled.height)

def parse_and_draw_detections(request):
    """Analyse the detected objects in the output tensor and draw them on the main output image."""
    parse_detections(request)
    draw_detections(request)

def parse_detections(request, stream='main'):
    """Parse the output tensor into a number of detected objects, scaled to the ISP out."""
    request.detections = []
    output_tensor = request.get_metadata().get('Imx500OutputTensor')
    if output_tensor:
        coords_list = np.array_split(output_tensor[: 4 * MAX_DETECTIONS], 4)
        categories = output_tensor[MAX_DETECTIONS * 4:MAX_DETECTIONS * 5]
        confs = output_tensor[MAX_DETECTIONS * 5:MAX_DETECTIONS * 6]
        request.detections = [Detection(coords, category, conf, request, stream)
                              for coords, category, conf in zip(zip(*coords_list), categories, confs)
                              if conf > CONF_THRESHOLD]

def draw_detections(request, stream='main'):
    """Draw the detections for this request onto the ISP output."""
    with MappedArray(request, stream) as m:
        for detection in request.detections:
            x, y, w, h = detection.box
            label = f"{LABELS[int(detection.category)]} ({round(detection.conf, 2)})"
            cv2.putText(m.array, label, (x + 5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.rectangle(m.array, (x, y), (x + w, y + h), (0, 255, 0, 0))


# This must be called before instantiation of Picamera2
IVS.set_network_firmware("/home/pi/imx500_network_firmware/imx500_network_mobilenet_ssd.fpk")

picam2 = Picamera2()
config = picam2.create_preview_configuration(controls={'FrameRate': 30})
picam2.start(config, show_preview=True)
picam2.pre_callback = parse_and_draw_detections

cv2.startWindowThread()
while True:
    input_tensor = picam2.capture_metadata()['Imx500InputTensor']
    cv2.imshow("Input Tensor", IVS.input_tensor_image(input_tensor, INPUT_TENSOR_SIZE, (384, 384, 384), (0, 0, 0)))
    cv2.resizeWindow("Input Tensor", *INPUT_TENSOR_SIZE)
