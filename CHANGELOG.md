# Change Log

## Unreleased (on "next" branch)

### Added

### Changed

## 0.3.8 Beta Release 7

### Added

* Support for cameras that have autofocus integrated properly with libcamera.
* New switch_mode_and_capture_request method.

### Changed

* Fewer frame drops when recording videos.
* Fixes when closing a preview window with the mouse.

## 0.3.7 Beta Release 6

### Added

* Ability to control via the configuration "queue" parameter whether Picamera2 keeps hold of the last completed request or not. This means you may wait marginally longer for a capture in some use cases, but also that the system cannot give you the frame that arrived slightly before you requested it.

### Changed

* The `Picamera2.start_encoder` function prototype has been made very similar to `Picamera2.start_recording` for consistency. Most existing calls still work, but there are a few call patterns that may need updating. The new prototype is: `start_encoder(self, encoder=None, output=None, pts=None, quality=Quality.MEDIUM)`
* The `Picamera2.wait` function now requires an argument, which is the "job" that was returned to you when you made the asynchronous call, for example instead of
```
picam2.capture_file("test.jpg", wait=False)
metadata = picam2.wait()
```
you would use
```
job = picam2.capture_file("test.jpg", wait=False)
metadata = picam2.wait(job)
```
Please also refer to our updated Qt examples.
* Some bug fixes when starting and stopping encoders.
* Risk of video frame drops during transient busy periods reduced.

## 0.3.6 Beta Release 5

### Added

* The `Picamera2.global_camera_info()` method will return information about all the attached cameras.
* We have introduced the ability to control multiple Picamera2 objects (all opened for different cameras) within the same Python process. They behave independently and can each have their own preview window.
* There is now limited support for USB webcams that deliver MJPEG or YUYV streams. Images can be displayed by the QT (not QTGL) preview.
* Picamera2 objects have a title_fields property which can be set to a list of the metadata fields to display on the preview window title bar (for example `picam2.title_fields = ["ExposureTime", "AnalogueGain"]).

### Changed

* Resources are freed more reliably when Picamera2 objects are closed.

## 0.3.5 Beta Release 4

### Added

### Changed

* Add support for outputting timestamps when using the JPEG encoder for video.
* Fix a bug which prevented the mjpeg_server.py example from working. This has also been added to the automatic test suite so shouldn't get broken again!

## 0.3.4 Beta Release 3

### Added

* Ability to record uncompressed or raw video frames.

### Changed

* Releasing of camera resources has been made more reliable, so once the Picamera2 object has been closed it can be re-opened more reliably (optionally by other processes).
* Logging has been revised to work better with applications already using Python logging.
* Some reporting of, and recovery from, certain error conditions has been improved.
* Large encoded video frames are now split automatically for streaming over UDP.

## 0.3.3 Beta Release 2

### Added

### Changed

* Very minor changes for the latest version of libcamera. "libcamera.ColorSpace.Jpeg()" has become "libcamera.ColorSpace.Sycc()".

## 0.3.2 Beta Release 1

### Added

* All the preview implementations now support a "display transform", allowing the preview image to be horizontally and/or vertically flipped (whilst not affecting the underlying image). The Picamer2.start_preview method allows a libcamera transform to be passed.
* Added APIs to capture and copy buffers/arrays from multiple streams at once: capture_buffers, capture_arrays, switch_mode_and_capture_buffers, switch_mode_and_capture_arrays.
* Allow entries from the sensor_modes property to be used directly as the raw stream configuration.
* Support for version 2.0 tuning files, including a find_tuning_algo method to make them easier to use.
* Demo Qt applications have been moved out of the examples folder to apps. A new "app_full.py" exists which allows phots and videos to be recorded, and gives control through a GUI of various camera and image tuning parameters.
* Added a sensor_modes field to the Picamera2 object. This can be queried to find out exactly what raw camera modes are supported, giving details of the maximum framerate and the field of view.

### Changed

* Installation through pip now avoids installing the Qt and OpenGL dependencies by default. If you want them, use "pip3 install picamera2[gui]" or just do "sudo apt install -y python3-qt5 python3-opengl" first.
* Fixed bug displaying overlays using DRM (pykms seems to have changed underneath us).
* There's been some refactoring which has changed the way asynchronous calls (with wait=False) work. You should now call picam2.wait() to obtain the result, and you can set the signal_function so that you can avoid calling it before it's finished. The previous fields like "async_result" have been removed.
* JpegEncoder defaults to producing YUV420 output now, though the constructor allows other colour subsampling modes to be chosen.
* Fix bug where framerates had to be integer values.
* Fix typo in align_configuration method.
* Allow in-place image manipulation (using the MappedArray class) even when the image rows have padding.

## 0.2.3 Alpha Release 3

### Added

* High level API functions "start_and_capture_file/files", "start_and_record_video" are added for users who need to know less about the Picamera2 internals.
* A very trivial Metadata class is provided that can be used to wrap the metadata dictionaries, for those that prefer this style.
* A Controls class is provided which gives an object-like view to control lists. The class is able to check that the control names are valid.
* Configuration structures are provided so that the Picamera2 object can be configured using the "object" style. Three such instances are embedded in the Picamera2 object, namely preview_configuration, still_configuration and video_configuration.

### Changed

* The start_recording() method accepts an optional configuration.
* The start_preview() method accepts True as an indication to try and autodetect the correct type of preview window. Note that there will be situations where it guesses incorrectly.
* The start() method can optionally be given config and show_preview parameters which will configure the camera and start the preview (if it isn't running already).
* Streams no longer have their widths optimally aligned by default. A separate align_configuration() method can be called to enforce this.
* The preview_configuration(), still_configuration() and video_configuration() methods (xxx_configuration) are renamed to create_xxx_configuration().

## 0.2.2 Alpha Release 2

### Added

* The QPicamera2 widget will now display YUV420 images if the cv2 (OpenCV) module is installed.
* Methods that allow still captures to be saved to files have been updated to accept file-like objects, such as BytesIO.
* NOGUI=1 environmental variable to install without GUI dependencies
* The Picamera2's request_callback has been changed to post_callback. A new pre_callback has been added which runs before images copied for applications.
* Support for multiple outputs for the encoder

### Changed

* The still_configuration defaults now specify the default display and encode streams as none. The resolutions are often so large that the images can be problematic and there are often better alternatives (e.g. specifying a lores stream and displaying that instead).
* The preview window implementations are changed to preserve image aspect ratios which they did not previously. The Qt variants also respect resize events.

## 0.2.1 Alpha Release

### Added

* Everything installable via apt and pip.
* Many new examples.

### Changed

* Revised API - please refer to README.md file and examples.

## 0.1.1 Pre-Alpha Release
