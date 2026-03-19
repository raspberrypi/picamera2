#!/bin/python3

import os

try:
    from picamera2.devices import Hailo, hailo_architecture
except ImportError:
    print("SKIPPED (hailo_platform not installed)")
    quit()

from picamera2 import Picamera2

# Check a Hailo device is present.
arch = hailo_architecture()
if arch is None:
    print("SKIPPED (no Hailo device found)")
    quit()

# Pick models based on architecture.
if arch == 'HAILO10H':
    detect_model = '/usr/share/hailo-models/yolov8m_h10.hef'
    pose_model = '/usr/share/hailo-models/yolov8s_pose_h10.hef'
else:
    detect_model = '/usr/share/hailo-models/yolov8s_h8l.hef'
    pose_model = '/usr/share/hailo-models/yolov8s_pose_h8l_pi.hef'

if not os.path.exists(detect_model):
    print("SKIPPED (detection model not found:", detect_model + ")")
    quit()
if not os.path.exists(pose_model):
    print("SKIPPED (pose model not found:", pose_model + ")")
    quit()

NUM_FRAMES = 30

# Test detection model over 30 frames.
print("Testing detection model:", detect_model)
with Hailo(detect_model) as hailo:
    input_shape = hailo.get_input_shape()
    print("Input shape:", input_shape)
    if len(input_shape) != 3:
        print("ERROR: expected 3-dimensional input shape, got", len(input_shape))

    inputs, outputs = hailo.describe()
    print("Model inputs:", len(inputs), "outputs:", len(outputs))
    if len(inputs) < 1:
        print("ERROR: expected at least 1 input layer")
    if len(outputs) < 1:
        print("ERROR: expected at least 1 output layer")

    with Picamera2() as picam2:
        model_h, model_w = input_shape[0], input_shape[1]
        config = picam2.create_preview_configuration(
            main={'size': (1920, 1080), 'format': 'XRGB8888'},
            lores={'size': (model_w, model_h), 'format': 'RGB888'}
        )
        picam2.configure(config)
        picam2.start()

        for i in range(NUM_FRAMES):
            frame = picam2.capture_array('lores')
            result = hailo.run(frame)
            if result is None:
                print("ERROR: detection inference returned None on frame", i)
                break
        else:
            print("Detection model: all", NUM_FRAMES, "frames returned results")

        picam2.stop()

# Test pose estimation model over 30 frames.
print("Testing pose model:", pose_model)
with Hailo(pose_model) as hailo:
    input_shape = hailo.get_input_shape()
    print("Input shape:", input_shape)

    with Picamera2() as picam2:
        model_h, model_w = input_shape[0], input_shape[1]
        config = picam2.create_preview_configuration(
            main={'size': (1920, 1080), 'format': 'XRGB8888'},
            lores={'size': (model_w, model_h), 'format': 'RGB888'}
        )
        picam2.configure(config)
        picam2.start()

        for i in range(NUM_FRAMES):
            frame = picam2.capture_array('lores')
            result = hailo.run(frame)
            if result is None:
                print("ERROR: pose inference returned None on frame", i)
                break
        else:
            print("Pose model: all", NUM_FRAMES, "frames returned results")

        picam2.stop()
