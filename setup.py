#! /usr/bin/env python3

# Copyright (c) 2021-2022 Raspberry Pi & Raspberry Pi Foundation
#
# SPDX-License-Identifier: BSD-2-Clause

from setuptools import setup, Extension
from os import getenv

with open("README.md") as readme:
    long_description = readme.read()

setup(
    name='picamera2',
    version='0.2.1',
    description='The libcamera-based Python interface to Raspberry Pi cameras, based on the original Picamera library',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Raspberry Pi & Raspberry Pi Foundation',
    author_email='picamera2@raspberrypi.com',
    url='https://github.com/RaspberryPi/picamera2',
    project_urls={
        'Bug Tracker': 'https://github.com/RaspberryPi/picamera2/issues',
    },
    license='BSD 2-Clause',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.9",
        "Topic :: Multimedia :: Graphics :: Capture :: Digital Camera",
    ],
    packages=['picamera2', 'picamera2.encoders', 'picamera2.outputs', 'picamera2.previews', 'picamera2.utils'],
    python_requires='>=3.9',
    licence='BSD 2-Clause License',
    install_requires=['numpy', 'PiDNG', 'piexif', 'pillow', 'pyopengl', 'PyQt5', 'simplejpeg', 'v4l2-python3', 'python-prctl'])
