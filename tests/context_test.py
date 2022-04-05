from PiCamera2.PiCamera2 import *

def main():
    print("With context...")
    time.sleep(1)
    with PiCamera2() as picam2:
        preview = picam2.preview_configuration()
        picam2.configure(preview)
        picam2.start()
        picam2.start_preview()
        metadata = picam2.capture_file("context_test.jpg")
        print(metadata)
    
    time.sleep(5)
    
    print("Without context...")
    time.sleep(1)
    picam2 = PiCamera2()
    preview = picam2.preview_configuration()
    picam2.configure(preview)
    picam2.start()
    picam2.start_preview()
    metadata = picam2.capture_file("no_context_test.jpg")
    print(metadata)
    picam2.stop_preview()
    picam2.close()


if __name__ == "__main__":
    main()
