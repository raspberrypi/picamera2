# Picamera2

---
This is a drastic refactor of _picamera2_ to a much smaller footprint and
feature set that emphasises consistant, reliable, imaging performance. 
Additonally, we use modern dev practices, established tools for test/lint.

## Installation

_picamera2_ is only supported on Raspberry Pi OS Bullseye (or later) images, both 32 and 64-bit. As of September 2022, _picamera2_ is pre-installed on images downloaded from Raspberry Pi. It works on all Raspberry Pi boards right down to the Pi Zero, although performance in some areas may be worse on less powerful devices.

_Picamera2_ is _not_ supported on:

* Images based on Buster or earlier releases.
* Raspberry Pi OS Legacy images.
* Bullseye (or later) images where the legacy camera stack has been re-enabled.

```
sudo apt install -y python3-libcamera
python setup.py install
```

## Contributing

Open a PR, discuss the changes. Our goals are brevity, maintainability,
and reliability. 

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
