from picamera2.picamera2 import Picamera2
import time


wait = 10
buffer = 1

def main():
    
    #First we create a camera instance.
    picam2 = Picamera2(log = True)
    
    #Let's set it up for previewing.
    preview = picam2.preview_configuration()
    picam2.configure(preview)
    
    
    picam2.start_camera()
    
    
    qtgl1 = time.monotonic()
    print("QT GL Preview")
    time.sleep(buffer)
    picam2.start_preview('QT GL')
    time.sleep(wait)
    picam2.stop_preview()
    qtgl2 = time.monotonic()
    
    null1 = time.monotonic()
    print("Null Preview")
    time.sleep(buffer)
    picam2.start_preview('nuLL')
    time.sleep(wait)
    picam2.stop_preview()
    null2 = time.monotonic()
    
    
    qt1 = time.monotonic()
    print("QT Preview")
    time.sleep(buffer)
    picam2.start_preview('Qt')
    time.sleep(wait)
    picam2.stop_preview()
    qt2 = time.monotonic()
    
    
    # drm1 = time.monotonic()
    # print("DRM Preview")
    # time.sleep(1)
    # picam2.start_preview('drm',x=100,y=100)
    # time.sleep(10)
    # picam2.stop_preview()
    # drm2 = time.monotonic()
    
    #Close the camera.
    picam2.close_camera()
    
    print(f"QT GL Cycle Results: {qtgl2-qtgl1-wait-buffer} s")
    print(f"Null Cycle Results: {null2-null1-wait-buffer} s")
    print(f"QT Cycle Results: {qt2-qt1-wait-buffer} s")



if __name__ == "__main__":
    main()