#! /usr/bin/env python3

# Copyright (c) 2021-2022 Raspberry Pi & Raspberry Pi Foundation
#
# SPDX-License-Identifier: BSD-2-Clause

from setuptools import setup, Extension
from os import getenv

with open("README.md") as readme:
    long_description = readme.read()

setup(name='picamera2',
      version='0.1.0',
      description='picamera2 library',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Raspberry Pi & Raspberry Pi Foundation',
      author_email='picamera2@raspberrypi.com',
      url='https://github.com/RaspberryPi/picamera2',
      project_urls={
          'Bug Tracker': 'https://github.com/RaspberryPi/picamera2/issues',
      },
      packages=['picamera2', 'picamera2.encoders', 'picamera2.previews', 'picamera2.utils'],
      python_requires='>=3.7',
      licence='BSD 2-Clause License',
      install_requires=['numpy', 'PyQt5', 'pyopengl', 'piexif', 'simplejpeg', 'pillow', 'v4l2-python3'])