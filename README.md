# SciCamera

---
Consistent and reliable imaging for scientific applications.


## Why _SciCamera_?

Scientific imaging applications often require minimal post-processing pipelines, 
precise capture timing, near-gapless sequential frames, and easily 
configurable settings like gain, resolution, bit-depth, and exposure 
length. 

This project, which began as fork of the webcam/video-focused [`picamera2`][picamera2]
library, aims to make it easy to configure and use cameras for scientific applications,
with a focus on _performance, reliability, code quality, and maintainability_.


### Why not _SciCamera_?

SciCamera currently focuses on high-quality, timing-sensitive, minimally-processed
_still images_. For low-bandwidth, real-time image and video streaming, we recommend 
the [`picamera2`][picamera2] library.


## Platform support

_SciCamera_ supports

- Raspberry Pi OS (Bullseye or later), 64-bit.
- x86 Ubuntu

Other debian flavors are likely to be supported. We welcome pull requests to extend
the testing toolchains to cover your platform.

## Installation

_SciCamera_ is a pure python package, but relies on the python
c++ wrapper of _libcamera_.

_SciCamera_ can be installed simply with:
```
pip install scicamera
```

### Installing libcamera + python bindings

Import and use of the above pacakge requires that `libcamera` to be built
with the python package enabled. On rasbian, this is accomplished by 
installing the `libcamera` package from apt. In x86 it must be built 
using something like the following:

```bash
git clone https://github.com/Exclosure/libcamera.git
cd libcamera
git checkout v0.0.4
meson setup build -D pycamera=enabled
ninja -C build
sudo ninja -C build install
```

## Bugs/Contributing


Open an issue/PR to discuss your bug or feature. Once a course of action
has been identified, open a PR, discuss the changes. 

Feature creep is not of interest, but we would be happy
to help you build your more complicated project on top of this.

If we like them, and the tests pass we will merge them. 
CI requires code has been processed `isort` and `black` toolchains.

Doing this is pretty easy:
```
isort .
black .
```

Great work.

## Publishing to PYPI

Should be added to github action later

1. Add your pypi token
  ```sh
  $ poetry config pypi-token.pypi my-token
  ```

2. Cut a new tag
  ```sh
  $ git tag -a v0.1.0 -m "Version 0.1.0"
  $ git push origin v0.1.0
  ```

3. Publish
  ```sh
  $ poetry publish --build
  ```


[picamera2]:https://github.com/raspberrypi/picamera2
