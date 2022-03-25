# Picamera2

---
**WARNING!** *Picamera2* is currently available here as a **preview release**. There will be bugs and problems, and both the implementation and public API are likely to change significantly and without warning. It is provided only for experimentation and not for any purposes that require any degree of stability.
---

*Picamera2* is the libcamera-based replacement for *Picamera* which was a Python interface to the Raspberry Pi's legacy camera stack. *Picamera2* also presents an easy to use Python API.

For the time being, the documentation here is mostly based on a number of supplied example programs. These are listed and discussed [below](#examples).

## Installation

These instructions are for a fresh 32-bit Bullseye image running on a Pi 4B. On other platforms your mileage may vary - good luck.

First install and build *libcamera* according to the [standard instructions](https://www.raspberrypi.com/documentation/accessories/camera.html#building-libcamera) but with the following *two* differences:

1. Clone the picamera2 branch from the libcamera repo `https://github.com/raspberrypi/libcamera.git` (not from the usual location). You can use the command
```
git clone --branch picamera2 https://github.com/raspberrypi/libcamera.git
```
WARNING: DO NOT USE THIS REPOSITORY FOR ANY PURPOSE OTHER THAN TRYING OUT *PICAMERA2* - IT WILL NOT BE KEPT UP TO DATE WITH MAINLINE *LIBCAMERA* DEVELOPMENT AND WILL BE DELETED IN DUE COURSE.

2. When configuring `meson`, add the option `-Dpycamera=enabled`.

Next we need some DRM/KMS bindings:

```
cd
git clone https://github.com/tomba/kmsxx.git
cd kmsxx
git submodule update --init
sudo apt install -y libfmt-dev libdrm-dev
meson build
ninja -C build
```

You will also need the python-v4l2 module. The official version is hopelessly out of date and appears to be unmaintained for many years, so please install the fork below:

```
cd
git clone https://github.com/RaspberryPiFoundation/python-v4l2.git
```

Finally fetch the *Picamera2* repository. There are a couple of dependencies to download first.

```
cd
sudo pip3 install pyopengl piexif
sudo apt install -y python3-pyqt5
git clone https://github.com/raspberrypi/picamera2.git
```

To make everything run, you will also have to set your `PYTHONPATH` environment variable. For example, you could put the following in your `.bashrc` file:
```
export PYTHONPATH=/home/pi/picamera2:/home/pi/libcamera/build/src/py:/home/pi/kmsxx/build/py:/home/pi/python-v4l2
```

**OpenCV**

OpenCV can be installed from `apt` as follows. Normally this should avoid the very long build times that can sometimes be required by other methods.

```
sudo apt install -y python3-opencv
sudo apt install -y opencv-data
```

## Contributing

We are happy to receive pull requests that will fix bugs, add features and generally improve the code. If possible, pull requests would ideally be:

- Restricted to one change or feature each.
- The commit history should consist of a number of commits that are as easy to review as possible.
- Where changes are likely to be more involved, we would invite authors to start a discussion with us first so that we can agree a good way forward.
- All the tests and examples should be working after each commit in the pull request. We'll shortly be adding some automated testing to the repository to make it easier to test if things have become broken.
- Any documentation should be updated accordingly. Where appropriate, new examples and tests would be welcomed.
- The author of the pull request needs to agree that they are donating the work to this project and to Raspberry Pi Ltd., so that we can continue to distribute it as open source to all our users. To indicate your agreement to this, we would ask that you finish commit messages with a blank line followed by `Signed-off-by: Your Name <your.email@your.domain>`.
- We'd like to conform to the common Python _PEP 8_ coding style wherever possible. To facilitate this we would recommend putting
```
#!/bin/bash

exec git diff --cached | ./tools/checkstyle.py --staged
```
into your `.git/hooks/pre-commit` file.

Thank you!

## How *Picamera2* Works

Readers are recommended to refer to the supplied [examples](#examples) in conjunction with the descriptions below.

### Opening the Camera

The camera system should be opened as shown.

```
from picamera2.picamera2 import *

picam2 = Picamera2()
```

Multi-camera support will be added in a future release.

### Configuring the Camera

The imaging hardware on the Pi is capable of supplying up to 3 image streams to an application.

1. There is always a *main* stream.
2. Optionally there may be a second low resolution stream (referred to as the *lores* stream). Both dimensions of this stream must be no larger than the main stream. The *lores* stream must always have a YUV (not RGB) type of pixel format - this is a hardware limitation.
3. Optionally an application may request a *raw* stream, consisting of the raw Bayer data received from the sensor before processing by the ISP.

After opening the camera, *Picamera2* must be configured with the `Picamera2.configure` method. It provides three methods for generating suitable configurations:

- `Picamera2.preview_configuration` generates configurations normally suitable for camera preview.
- `Picamera2.still_configuration` generates configurations normally suitable for still image capture.
- `Picamera2.video_configuration` generates configurations for video recording.

In all cases, these functions can generate configurations with no user arguments at all. Otherwise the user may supply the following parameters:

- `main` - description for the main stream. These are supplied as dictionaries. The most common entries are for the image size (`"size"`) and pixel format (`"format"`). A main stream is always generated, whether or not this parameter is supplied.
- `lores` - request a low resolution stream. This argument has the same format as `main`. If not specified, no low resolution stream will be generated.
- `raw` - request a raw stream. Again this argument has the same format, though the pixel format (`"format"`) will be supplied for you. If not specified, no raw stream will be available.

All three methods optionally also allow the following to be specified. They apply to all the configured streams.

- `transform` - the images may be horizontally or vertically flipped.
- `colour_space` - the colour space of the returned images (ignored for any raw stream).
- `buffer_count` - the number of buffers to allocate. The camera system always requires buffers to be available when the sensor starts to deliver a new frame, so having too few buffers can cause frames to be dropped.

These methods return the *camera configuration*. This may be further amended by the application before passing it to the `Picamera2.configure` function.

Examples:

Configure a default resolution preview.
```
config = picam2.preview_configuration()
picam2.configure(config)
```

Configure for a full resolution capture.
```
config = picam2.still_configuration()
picam2.configure(config)
```

Here we configure both a VGA preview (*main*) stream, and a QVGA low resolution (*lores*) stream.
```
config = picam2.preview_configuration(main={"size": (640, 480)},
                                      lores={"size": (320, 240), "format": "YUV420"})
picam2.configure(config)
```

Ask for an additional raw stream at the sensor resolution. This will force the camera to run at the maximum resolution, probably at a reduced framerate. Without the size parameter (just `raw={}`) the raw frame would be the one that *libcamera* would naturally choose for the resolution of the main stream (probably much smaller).
```
config = picam2.preview_configuration(raw={"size": picam2.sensor_resolution})
picam2.configure(config)
```

Rotate all the images by 180 degrees.
```
config = picam2.preview_configuration(transform=libcamera.Transform(hflip=1, vflip=1))
picam2.configure(config)
```

Still image capture normally configures only a single buffer, as this is all you need. But if you're doing some form of burst capture, increasing the buffer count may enable the application to receive images more quickly.
```
config = picam2.still_configuration(buffer_count=3)
picam2.configure(config)
```

### Driving the Camera

The *Picamera2* class implements most of the camera functionality, however, it does not run an *event loop* which feeds image buffers in and out of *libcamera*. The application has a number of choices:

- Use the `QtPreview` or `QtGlPreview` class. This starts a preview window implemented using *PyQt* and the Qt event loop drives the camera.
- Use the `DrmPreview` class. This should be used to render a preview window using DRM/KMS (i.e. when not running X Windows).
- Use the `NullPreview` class. This class actually generates no preview window at all and merely supplies an event loop that drives the camera.
- In a Qt application, the `QPicamer2` or `QGlPicamera2` widgets are provided and automatically use the Qt event loop to drive the camera.

To start the event loop, the `start_preview` method should be called. It can be passed an actual preview object, or for convenience can be passed one of the Preview enum values (see below). If given no arguments at all, a `NullPreview` is created. When running under a Qt even loop, `start_preview` should _not_ be called at all.

Example:

```
from picamera2.picamera2 import *

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

config = picam2.preview_configuration()
picam2.configure(config)

picam2.start()
```

Note that
```
from picamera2.previews.qt_gl_preview import *
picam2.start_preview(QtGlPreview())
```
is equivalent to `picam2.start_preview(Preview.QTGL)`.

To use the DRM preview window, use `picam2.start_preview(Preview.DRM)` instead.

To use the Qt (non-GL) preview window, use `picam2.start_preview(Preview.QT)` instead.

For no preview window at all, use `picam2.start_preview()` or `picam2.start_preview(Preview.NULL)`.

Please refer to the supplied examples for more information.

### Requests and Capturing

*libcamera* works by receiving *requests* from an application and returning them once they have been completed. Most simply, a *request* contains a buffer for each of the configured streams and completing the request means filling each of the buffers with an image from the camera. All the images in a request are created from a single raw frame from the sensor.

In the *Picamera2* framework most of this hidden from the application, and users can concentrate simply on capturing images. But if they want, applications can capture an entire *completed request*. From this it can extract images for all the configured streams as well as the *metadata*, namely the parameters of the system (exposure time, gain, and so on) used to capture those images.

When an application captures a request, that request can no longer be re-used by the camera system until the application *returns* it using the request's `release` method. If requests are repeatedly captured and not returned, the risk is that camera frames will start to be dropped and ultimately it can stall completely.

A limitation of capturing requests is that they only remain valid until the camera is re-configured (by another call to `Picamera.configure`), or the `Picamera2` object is deleted.

To capture a *PIL* image:
```
image = picam2.capture_image()
# The image is a copy and belongs to the application here.
```

To capture an image as a *numpy* array:
```
np_array = picam2.capture_array()
# Also a copy.
```

If the *lores* stream is configured for YUV420 images, these can't be represented directly as a single 2d *numpy* array. For this reason we can only capture it as a "buffer", meaning a single long 1d array, where the user could access the 3 colour channels by *slicing*. Thus:
```
lores_buffer = picam2.capture_buffer("lores")
config = picam2.stream_configuration("lores")
(w, h) = config["size"]
stride = config["stride"]
num_pixels_Y = stride * h
num_pixels_UV = num_pixels_Y // 4
Y = lores_buffer[:num_pixels_Y].reshape(h, stride)
U = lores_buffer[num_pixels_Y:num_pixels_UV].reshape(h//2, stride//2)
V = lores_buffer[num_pixels_Y+num_pixels_UV:num_pixels_UV].reshape(h//2, stride//2)
```

For the raw image:
```
raw_np_array = picam2.capture_array("raw")
```

To capture a complete request:
```
request = picam2.capture_request()
# This request has been taken by the application and can now be used, for example
request.save("main", "test.jpg")
# Once done, the request must be returned.
request.release()
```

When switching to a full resolution capture, it's common to re-start the camera in preview mode afterwards. When capturing a whole request, however, you can't re-start the camera until you're finished with that request:
```
capture_config = picam2.still_configuration()
request = picam2.switch_mode_capture_request_and_stop(capture_config)
# The camera is stopped but we can use the request. Then return the request:
request.release()
# And the camera could be re-configured and restarted.
preview_config = picam2.preview_configuration()
picam2.configure(preview_configuration)
picam2.start()
```

## Examples

A number of small example programs are provided in the [`examples`](examples) folder. Users who are new to *Picamera2* should probably start with the following:

- [`preview.py`](#previewpy) - how to start a preview window. Also check out the other `preview_*.py` examples.
- [`capture_jpeg.py`](#capture_jpegpy) - how to capture a JPEG image.
- [`capture_full_res.py`](#capture_full_respy) - how to capture a full resolution JPEG image. Also check out the other `capture_*.py` examples.

Once you've looked at these, you might like to investigate some further topics:

- [`capture_image_full_res.py`](#capture_image_full_respy) - you can capture *PIL* images or *numpy* arrays, not just JPEG or PNG files.
- [`metadata.py`](#metadatapy) - how to find out the camera's current parameters. Also look at [`metadata_with_image.py`](#metadata_with_imagepy) to see how to capture the exact parameters that apply to a specific image.
- [`controls.py`](#controlspy) and [`exposure_fixed.py`](#exposure_fixedpy) for how to set the camera controls for yourself, either while it's running or when it starts.
- [`capture_video.py`](#capture_videopy) shows you how to capture an h.264 video file.

Finally, for more advanced use cases:

- If you're interested in using *OpenCV* with Python `cv2`, please look at, for example, [`opencv_face_detect.py`](#opencv_face_detectpy).
- If you'd like to embed camera functionality in a *PyQt* application, please look at [`app_capture.py`](#app_capturepy).
- To find out how and why you might want to use a low resolution ("lores") stream, please look at [`opencv_face_detect_2.py`](#opencv_face_detect_2py).
- To capture raw camera buffers, please see [`raw.py`](#rawpy).
- For an example of how you might capture and stream h.264 video over the network, please check [`capture_stream.py`](#capture_streampy).

### [app_capture.py](examples/app_capture.py)

This is a very simple *PyQt* application. It creates a camera preview widget that uses OpenGL hardware acceleration (the `QGlPicamera2` widget). This widget drives the camera processing. A button is hooked up to do a full resolution JPEG capture - the implementation of this is all hidden within the `Picamera2` object which has processing requests forwarded to it by the `QGlPicamera2` widget.

We also use the `Picamera2` object's *request callback*, which is called whenever an image is about to be displayed in the preview pane. Here we just fetch the camera's current parameters (the *metadata*) and write all of the information to a text pane.

### [capture_full_res.py](examples/capture_full_res.py)

This application starts a preview window and then performs a full resolution JPEG capture. The preview normally uses one of the camera's faster readout modes, so we have to pick a separate *capture* mode, and *switch* to it, for the final capture.

The `Picamera2.preview_configuration` method is best for selecting camera modes suitable for previewing, and `Picamera2.still_configuration` is best for selecting high resolution still capture modes.

### [capture_image_full_res.py](examples/capture_image_full_res.py)

This is very similar to [capture_full_res.py](#capture_full_respy) except that we capture a *PIL* ("Python Image Library") image object rather than a JPEG.

### [capture_jpeg.py](examples/capture_jpeg.py)

This is the simplest way to capture a JPEG. It starts a preview window and then captures a JPEG, whilst still running the camera in its preview mode. It does not switch over to the full resolution capture mode (for which see [capture_full_res.py](#capture_full_respy)).

### [capture_png.py](examples/capture_png.py)

Like [capture_jpeg.py](#capture_jpegpy), only it saves a PNG file rather than a JPEG.

### [capture_stream.py](examples/capture_stream.py)

Only slightly more complicated than capturing video to a file, we can route the output of the hardware video encoder to a network socket instead.

### [capture_video.py](examples/capture_video.py)

This is pretty much the simplest way to capture and encode the images into an h.264 file.

### [controls.py](examples/controls.py)

Camera control values can be updated while the camera is running. In this example we fix the camera's exposure time, gain and white balance values so that, after the controls have been set, the camera will no longer adapt these parameters to the operating environment.

### [controls_2.py](examples/controls_2.py)

This is an easier way to fix the gains and white balance - the AGC/AEC and AWB algorithms can simply be turned off.

### [exposure_fixed.py](examples/exposure_fixed.py)

Camera control values can be updated while the camera is running, but they can also be set when the camera starts, as we see here. Setting the exposure time and gain when it starts is particularly useful, because it means that the very first frame we capture will have these values. (Once the camera is running, it normally takes "a few frames" for such values to take effect.)

Note that the exposure time control takes an *integer* and not a *floating point* value. The analogue gain, however, will accept either.

### [metadata.py](examples/metadata.py)

While the camera is running, we can query its current settings, known as the *metadata*.

### [metadata_with_image.py](examples/metadata_with_image.py)

In [metadata.py](#metadatapy) we see how to get the current state of the camera. But in actual fact, these values are obtained from a particular image. If we then ask to capture an image we're not guaranteed that this new image will have exactly the same values. We can solve this problem by capturing a *request* instead.

Libcamera works by having applications submit *requests*, and it returns them to the application once it has filled all the image buffers in the request. All the images in a request come from the same camera image. *Picamera2* lets us capture one of these requests, so this contains all the images for the streams that we configured, and the metadata for that capture.

In this example, we capture a whole request. This request now belongs to us and libcamera cannot refill it until we return that request. So we now extract images and the associated metadata, knowing that they belong together. Once we're done, we *must* return the request to libcamera, using the `release` method. If we keep capturing requests without returning them, the camera system may start to drop frames and will ultimately stall completely if it has no buffers left in which to put camera images.

### [mjpeg_server.py](examples/mjpeg_server.py)

This is a simple MJPEG web server, derived from one of the old [*Picamera examples*](https://picamera.readthedocs.io/en/release-1.13/recipes2.html#web-streaming). You will need to install *simplejpeg* (`pip3 install simplejpeg`) as the existing JPEG encoders in *PIL* and *OpenCV* are not particularly convenient.

At some point in the future *Picamera2* may include built-in support for JPEG encoding, so this example is certainly liable to change.

To try it, just start the server on your Pi and then, on a different computer open a web browser and visit `http://<your-Pi's-IP-address>:8000`.

### [opencv_face_detect.py](examples/opencv_face_detect.py)

Face detection is very easy using *OpenCV* (the Python `cv2` module). Note how, in this example, we use the `NullPreview`. This drives the camera system but without displaying a preview window, because we're going to use *OpenCV* to display the images too.

The image has to be converted to greyscale for face detection, and then we draw face boxes on the original colour images that we display.

### [opencv_face_detect_2.py](examples/opencv_face_detect_2.py)

This is a more sophisticated version of [opencv_face_detect.py](#opencv_face_detectpy). There are two critical differences.

Firstly, we define a second lower resolution ("lores") image stream. A constraint in the Pi's hardware is that such a stream has to be encoded with YUV colour values rather than RGB. But this is quite useful because we can turn the Y plane of this image into the greyscale image that *OpenCV*'s face detector wants.

Secondly, we're using *Picamera2*'s hardware accelerated preview window, which renders frames at the full camera rate. Luckily, *Picamera2* gives us a *request callback* which is called upon every request before it is shown in the preview window, and runs in the camera thread also at the camera framerate. The callback here has been defined to draw the face boxes directly into the camera's image buffer.

The net effect is to run the preview, with face locations, at the full camera rate, although the actual locations of these face boxes only update at the rate that *OpenCV* can manage. We can also, as in this example, run the face detection on a different resolution from the preview image.

But please note that we generally advise **against** doing too much processing within the request callback function.

### [opencv_mertens_merge.py](examples/opencv_mertens_merge.py)

In this example we use the `NullPreview` so as to drive the camera system without a preview window, and supply controls to the `start` method (as in [exposure_fixed.py](#exposure_fixedpy)) so as to get pre-determined exposure values. Finally we use *OpenCV*'s *Mertens merge* image fusion method to get HDR-like images.

### [preview.py](examples/preview.py)

Starts a camera preview window. In this case we use the `QtGlPreview` to display the images. This implementation uses GPU hardware acceleration which is therefore normally the most efficient way display them (through X Windows).

### [preview_drm.py](examples/preview_drm.py)

Displays a preview window when running without X Windows, that is, in console mode (or you can usually suspend X Windows with Ctrl+Alt+F1). It uses Linux DRM/KMS to render the images. On a lower powered device such as a Pi Zero, this would be the recommended way to show camera images with good performance.

### [preview_x_forwarding.py](examples/preview_x_forwarding.py)

Whilst we normally recommend the use of the `QtGlPreview`, the GPU hardware acceleration doesn't work with X forwarding. This would typically include users who are logged into their Pi via ssh and wish to display the preview back on their local machine. In these cases the `QtPreview` should be used instead. It uses software rendering and is therefore more taxing on the Pi's CPU cores.

### [raw.py](examples/raw.py)

This example requests the raw stream alongside the main one, and shows how you would capture an image.

### [rotation.py](examples/rotation.py)

*Picamera2* allows horizontal or vertical flips to be applied to camera images, or both together to give a 180 degree rotation.

### [switch_mode.py](#examples/switch_mode.py)

Example of how to switch between one camera mode and another. In this case we reduce the number of very large buffers (for the "other" configuration) down to 3 to save some memory.

### [switch_mode_2.py](examples/switch_mode_2.py)

Alternative example of how to switch camera modes (like [switch_mode.py](#switch_modepy)). Under the hood both methods are in fact doing exactly the same thing.

### [yuv_to_rgb.py](examples/yuv_to_rgb.py)

A limitation of the second "lores" output stream is that it has to be in a YUV format. Sometimes it might be convenient to have a reasonably sized preview window, but a much smaller RGB version (for example for passing to a neural network). This example shows how to convert a YUV420 image to the interleaved RGB form that *OpenCV* and *TensorFlow Lite* normally prefer.

The `YUV420_to_RGB` function takes a YUV420 image and creates an interleaved RGB output of half resolution, matching the resolution of the input U and V planes (but not of the Y). The image size that you pass in (which is the *input* image size) must include any *padding*. Padding on the end of image rows is quite common so that we can match the optimal alignments that the underlying image processing hardware requires. `YUV420_to_RGB` lets you remove any such padding at the end by passing the unpadded width as the `final_width` parameter.

### [zoom.py](examples/zoom.py)

Digital zoom is achieved using the `ScalerCrop` control, which takes a rectangle in the form `(offset_x, offset_y, width, height)` to specify which part of the full image we see in the output. The coordinates of this rectangle always correspond to the sensor at full resolution, which can be obtained using the `Picamera2.sensor_resolution` property.

The current value of the `ScalerScrop` can be read in the normal way from the camera's metadata. A value of all zeroes should be taken as meaning the full sensor resolution.

Notice how this example synchronises `ScalerCrop` updates with frames from the camera. Otherwise all the controls would be set at once, with the final value overwriting all the others - so the zoom, rather than occurring gradually, would happen in a single large jump.
