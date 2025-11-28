from picamera2 import Picamera2, Process


def run(request):
    format = request.config["main"]["format"]
    width = request.config["main"]["size"][0]
    height = request.config["main"]["size"][1]
    array = request.make_array("main")
    if format == "YUV420":
        print(f"YUV420 {width} {height} {array.shape}")
        assert array.shape == (height * 3 // 2, width)
    elif format in ("RGB888", "BGR888"):
        assert array.shape == (height, width, 3)
    elif format in ("XBGR8888", "XRGB8888"):
        assert array.shape == (height, width, 4)
    else:
        raise ValueError(f"Format {format} not supported")
    return (format, (width, height))


if __name__ == "__main__":
    formats = ["YUV420", "RGB888", "BGR888", "XBGR8888", "XRGB8888"]
    sizes = [(1920, 1080), (1280, 720), (640, 480), (800, 600)]
    for size in sizes:
        for format in formats:
            if format == "YUV420" and size == (800, 600):
                continue
            print(f"Testing format {format} and size {size}")
            picam2 = Picamera2()
            config = picam2.create_preview_configuration()
            config["main"]["format"] = format
            config["main"]["size"] = size
            picam2.configure(config)
            picam2.start()
            process = Process(run, picam2)
            with picam2.captured_request() as request:
                future = process.send(request)
            if future.result()[0] != format or future.result()[1] != size:
                raise ValueError(f"{format} {size} failed - got wrong format from camera")
            else:
                print(f"Format {format} {size} passed")
            process.close()
            picam2.stop()
            picam2.close()
