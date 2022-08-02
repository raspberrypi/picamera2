# Change Log

## Unreleased (on "next" branch)

### Added

### Changed

* There's been some refactoring which has changed the way asynchronous calls (with wait=False) work. You should now call picam2.wait() to obtain the result, and you can set the signal_function so that you can avoid calling it before it's finished. The previous fields like "async_result" have been removed.
* JpegEncoder defaults to producing YUV420 output now, though the constructor allows other colour subsampling modes to be chosen.

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
