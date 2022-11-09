# Picamera2

---
*Picamera2* is currently available here as a beta release. This means there may still be some issues and bugs which we shall work on fixing, and where users identify particularly useful features we may still consider implementing them. Mostly we shall be working on bugs, stability, support, examples and documentation, as well as keeping up with ongoing _libcamera_ development. There will also be quite a strong presumption _against_ making signficant code changes unless it seems absolutely necessary, especially any that break existing behaviour or APIs.
---

*Picamera2* is the libcamera-based replacement for *Picamera* which was a Python interface to the Raspberry Pi's legacy camera stack. *Picamera2* also presents an easy to use Python API.

You can find [documentation here](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf) which should help you to get started.

There are also many examples in the `examples` folder of this repository, and some further _Qt_ application examples in the `apps` folder.

## Installation

_Picamera2_ is only supported on Raspberry Pi OS Bullseye (or later) images, both 32 and 64-bit. As of September 2022, _Picamera2_ is pre-installed on images downloaded from Raspberry Pi. It works on all Raspberry Pi boards right down to the Pi Zero, although performance in some areas may be worse on less powerful devices.

_Picamera2_ is _not_ supported on:

* Images based on Buster or earlier releases.
* Raspberry Pi OS Legacy images.
* Bullseye (or later) images where the legacy camera stack has been re-enabled.

On Raspberry Pi OS images, _Picamera2_ is now installed with all the GUI (_Qt_ and _OpenGL_) dependencies. On Raspberry Pi OS Lite, it is installed without the GUI dependencies, although preview images can still be displayed using DRM/KMS. If these users wish to use the additional X-Windows GUI features, they will need to run
```
sudo apt install -y python3-pyqt5 python3-opengl
```
(No changes are required to _Picamera2_ itself.)

### Installation using `apt`

`apt` is the recommended way of installing and updating _Picamera2_.

If _Picamera2_ is already installed, you can update it with `sudo apt install -y python3-picamera2`, or as part of a full system update (for example, `sudo apt upgrade`).

If _Picamera2_ is not already installed, then your image is presumably older and you should start with
```
sudo apt update
sudo apt upgrade
```
If you have installed _Picamera2_ previously using `pip`, then you should also uninstall this (`pip3 uninstall picamera2`).

Thereafter, you can install _Picamera2_ _with_ all the GUI (_Qt_ and _OpenGL_) dependencies using
```
sudo apt install -y python3-picamera2
```
If you do _not_ want the GUI dependencies, use
```
sudo apt install -y python3-picamera2 --no-install-recommends
```

### Installation using `pip`

This is no longer the recommended way to install _Picamera2_. However, if you want to do so you can use
```
sudo apt install -y python3-libcamera python3-kms++
sudo apt install -y python3-pyqt5 python3-prctl libatlas-base-dev ffmpeg python3-pip
pip3 install numpy --upgrade
pip3 install picamera2[gui]
```
which will install _Picamera2_ with all the GUI (_Qt_ and _OpenGL_) dependencies. If you do not want these, please use
```
sudo apt install -y python3-libcamera python3-kms++
sudo apt install -y python3-prctl libatlas-base-dev ffmpeg libopenjp2-7 python3-pip
pip3 install numpy --upgrade
pip3 install picamera2
```

## Contributing

Please note that the "main" branch of this repository corresponds to the currently released version of _Picamera2_ so that the examples there can be referred to by users. Development for forthcoming releases happens on the "next" branch.

We are happy to receive pull requests (normally for the "next" branch) that will fix bugs, add features and generally improve the code. Pull requests should be:

- Restricted to one change or feature each. Please try to avoid "drive-by fixes" especially in a larger set of changes, as it can make them harder to review.
- The commit history should consist of a number of commits that are as easy to review as possible. In particular this means:
  - Where one commit is fixing errors in an earlier commit in the set, please simply merge them.
  - Where a commit is reverting a commit from earlier in the set, please remove the commit entirely.
  - Please avoid adding merge commits or any other unnecessary commits.
  - The commit message should have a short single line at the top which is nonetheless as descriptive as possible. After that we encourage more lines explaining in a little more detail exactly what has been done.
  - In general, we don't need to see all the trials, errors and bug-fixes that went into this change, we only want to understand how it works now!
  - Try to ensure that the automated tests are working after all the commits in the set. This avoids other developers going back to an arbitrary earlier commit and finding that things don't work. There can be occasions when other problems cause test failures beyond our control, so we'll just have to remain alert to these and work around them as best we can.
- Where changes are likely to be more involved, or may change public APIs, authors should start a discussion with us first so that we can agree a good way forward.
- Before submitting a pull request, please ensure that all the automated tests are passing. They can be run using the `tools/run_tests` script. Please use `tools/run_tests --help` for more information.
- Any documentation should be updated accordingly. New examples and tests should be included wherever possible. Also consider making an entry in the change log.
- The author of the pull request needs to agree that they are donating the work to this project and to Raspberry Pi Ltd., so that we can continue to distribute it as open source to all our users. To indicate your agreement to this, we would ask that you finish commit messages with a blank line followed by `Signed-off-by: Your Name <your.email@your.domain>`.
- We'd like to conform to the common Python _PEP 8_ coding style wherever possible. To facilitate this we would recommend putting
```
#!/bin/bash

exec git diff --cached | ./tools/checkstyle.py --staged
```
into your `.git/hooks/pre-commit` file. We note that there are some occasions when other formatting is actually better in which case please use that in spite of the style checker, but do note this in your pull request so that we understand.

Thank you!
