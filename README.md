# scicamera

---
This is a drastic refactor of _picamera2_ to a much smaller footprint and
feature set that emphasises consistant and reliable imaging performance. 

_scicamera_ is predominantly supported on:
- Raspberry Pi OS Bullseye (or later) images 64-bit.
- x86 Ubuntu (likely other debian flavors as well)

**Our goals are performance, reliability, brevity, and maintainability.**

## Installation

_scicamera_ is a pure python package, but relies on the python
c++ wrapper of _libcamera_.

_scicamera_ can be installed simply with:
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
