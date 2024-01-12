from picamera2.encoders import H264Encoder
from picamera2 import Picamera2, MappedArray
import cv2
import time
import threading

def apply_overlay(request):
    """pre_callback function that overlays the image on the video 
    """
 
    with MappedArray(request, "main") as m:
        
        frame = m.array
        # Overlay the image
        for c in range(0, 3):
            frame[0:OVERLAY_HEIGHT, 0:OVERLAY_WIDTH, c] = (
                OVERLAY_ALPHA * OVERLAY_COLOR[:, :, c] + (1 - OVERLAY_ALPHA) * frame[0:OVERLAY_HEIGHT, 0:OVERLAY_WIDTH, c]
            )
            
def update_overlay():
    """ gets the overlay image and resizes it if needed to fit the video """
    
    global OVERLAY_IMAGE
    global OVERLAY_WIDTH
    global OVERLAY_HEIGHT
    global OVERLAY_COLOR
    global OVERLAY_ALPHA
    
    while True:
        overlay_image = cv2.imread(OVERLAY_IMAGE_PATH, cv2.IMREAD_UNCHANGED)
        overlay_height, overlay_width = overlay_image.shape[:2] # for some reason height first in the array
        resize_overaly = False
        if overlay_width > WIDTH:
            overlay_width = WIDTH
            resize_overaly = True
        
        if overlay_height > HEIGHT:
            overlay_height = HEIGHT
            resize_overaly = True
            
        if resize_overaly:
            overlay_image = cv2.resize(overlay_image, (overlay_width, overlay_height))

        overlay_color = overlay_image[:, :, :3]
        overlay_alpha = overlay_image[:, :, 3] / 255.0            
        if overlay_image.shape[2] == 4:  # If the image has 4 channels
            overlay_color = cv2.cvtColor(overlay_color, cv2.COLOR_BGR2RGB)     
            
        OVERLAY_IMAGE, OVERLAY_WIDTH, OVERLAY_HEIGHT, OVERLAY_COLOR, OVERLAY_ALPHA = (
            overlay_image,
            overlay_width,
            overlay_height,
            overlay_color,
            overlay_alpha
        )
        time.sleep(OVERLAY_UPDATE_DELAY)
     

WIDTH = 1920
HEIGHT = 1080
OVERLAY_IMAGE_PATH = "/path/to/image.png"                 
OVERLAY_IMAGE = None
OVERLAY_WIDTH = None
OVERLAY_HEIGHT = None
OVERLAY_COLOR = None
OVERLAY_ALPHA = None
OVERLAY_UPDATE_DELAY = 1

update_overlay_thread = threading.Thread(target=update_overlay)
update_overlay_thread.start()


picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (WIDTH, HEIGHT)})
picam2.configure(video_config)
picam2.pre_callback = apply_overlay
encoder = H264Encoder(bitrate=10000000)
output = "output.mp4"

picam2.start_recording(encoder, output)
time.sleep(10)
picam2.stop_recording()
