# Change Log

## Unreleased

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
