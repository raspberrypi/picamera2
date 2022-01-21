#!/usr/bin/python3

# Mostly copied from https://picamera.readthedocs.io/en/release-1.13/recipes2.html
# Run this script, then point a web browser at http:<this-ip-address>:8000
# Note: needs simplejpeg to be installed (pip3 install simplejpeg).

import picamera2
import null_preview
import simplejpeg
import io
import logging
import socketserver
from threading import Condition, Thread
from http import server

PAGE="""\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""

output_frame = None
output_buffer = io.BytesIO()
output_condition = Condition()
output_running = True

def encode_thread():
    global output_frame
    while output_running:
        array = picam2.capture_array()
        buf = simplejpeg.encode_jpeg(array, colorspace='BGRX')
        output_buffer.truncate()
        with output_condition:
            output_frame = output_buffer.getvalue()
            output_condition.notify_all()
        output_buffer.seek(0)
        output_buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output_condition:
                        output_condition.wait()
                        frame = output_frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

picam2 = picamera2.Picamera2()
preview = null_preview.NullPreview(picam2)
picam2.configure(picam2.preview_configuration(main={"size": (640, 480)}))
picam2.start()
thread = Thread(target=encode_thread)
thread.start()

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    output_running = False
    thread.join()
    preview.stop()
    picam2.stop()
