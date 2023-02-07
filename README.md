# scicamera

---
This is a drastic refactor of _picamera2_ to a much smaller footprint and
feature set that emphasises consistant, reliable, imaging performance. 
Additonally, we use modern dev practices, established tools for test/lint.

## Installation

_scicamera_ is predominantly supported on Raspberry Pi OS Bullseye (or later) images, both 32 and 64-bit. Limited support is available on Ubuntu and other
debian flavors, but will require `libcamera` to be built with the python
package enabled.


## Contributing

Open a PR, discuss the changes. Our goals are performance, brevity, maintainability, and reliability. 

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
