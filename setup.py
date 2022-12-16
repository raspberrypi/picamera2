#! /usr/bin/env python3

# Copyright (c) 2021-2022 Raspberry Pi & Raspberry Pi Foundation
#
# SPDX-License-Identifier: BSD-2-Clause

from setuptools import setup

with open("README.md") as readme:
    long_description = readme.read()

setup(
    name="picamera2",
    version="0.3.7",
    description="The libcamera-based Python interface to Raspberry Pi cameras, based on the original Picamera library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Raspberry Pi & Raspberry Pi Foundation",
    author_email="picamera2@raspberrypi.com",
    url="https://github.com/RaspberryPi/picamera2",
    project_urls={
        "Bug Tracker": "https://github.com/RaspberryPi/picamera2/issues",
    },
    license="BSD 2-Clause",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.9",
        "Topic :: Multimedia :: Graphics :: Capture :: Digital Camera",
    ],
    packages=[
        "picamera2",
        "picamera2.encoders",
        "picamera2.outputs",
        "picamera2.previews",
    ],
    python_requires=">=3.9",
    licence="BSD 2-Clause License",
    install_requires=[
        "numpy",
        "pillow",
    ],
)
