#! /usr/bin/env python3

# Copyright (c) 2021-2022 Raspberry Pi & Raspberry Pi Foundation
#
# SPDX-License-Identifier: BSD-2-Clause

from setuptools import setup, Extension
from os import getenv

with open("README.md") as readme:
    long_description = readme.read()

setup(
    name='picamera2-lite',
    version='0.2.2',
    description='picamera2 without the gui stuff',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Raspberry Pi & Raspberry Pi Foundation',
    author_email='picamera2@raspberrypi.com',
    url='https://autosbc/picamera2-lite',
    project_urls={
        'Bug Tracker': 'https://github.com/autosbc/picamera2-lite/issues',
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
    packages=['picamera2-lite', 'picamera2-lite.encoders', 'picamera2-lite.outputs', 'picamera2-lite.previews', 'picamera2-lite.utils'],
    python_requires='>=3.9',
    licence='BSD 2-Clause License',
    install_requires=['simplejpeg', 'v4l2-python3'])
