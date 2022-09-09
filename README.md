# Picamera2

---
*Picamera2* is currently available here as a beta release. This means there may still be some issues and bugs which we shall work on fixing, and where users identify particularly useful features we may still consider implementing them. Mostly we shall be working on bugs, stability, support, examples and documentation, as well as keeping up with ongoing _libcamera_ development. There will also be quite a strong presumption _against_ making signficant code changes unless it seems absolutely necessary, especially any that break existing behaviour or APIs.
---

*Picamera2* is the libcamera-based replacement for *Picamera* which was a Python interface to the Raspberry Pi's legacy camera stack. *Picamera2* also presents an easy to use Python API.

You can find [documentation here](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf) which should help you to get started.

There are also many examples in the `examples` folder of this repository, and some further _Qt_ application examples in the `apps` folder.

## Installation

Please note that Raspberry Pi OS images released after August 2022 should contain _Picamera2_ pre-installed. However, if you do need to install or update _Picamera2_, please follow the instructions below.

These instructions are for a fresh 32-bit Bullseye image running on a Pi 4B but should work on other platforms too. Please perform a `sudo apt update` and `sudo apt upgrade` first if you have not done so recently.

At the time of writing (August 2022) we are about to release `apt` packages for _Picamera2_. Once these go live it will be sufficient simply to run
```
sudo apt install -y python3-picamera2
```
If, at the moment that you read this, the package is not yet published, you can install _Picamera2_ using:

```
sudo apt install -y python3-libcamera python3-kms++
sudo apt install -y python3-pyqt5 python3-prctl libatlas-base-dev ffmpeg python3-pip
pip3 install numpy --upgrade
pip3 install picamera2[gui]
```

Note that these two methods will both install all the GUI (Qt5 and OpenGL) dependencies. If you won't want those, please use:
```
sudo apt install -y python3-picamera2 --no-install-recommends
```
or, if that package is not yet published:

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
