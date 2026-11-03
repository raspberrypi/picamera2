#!/usr/bin/env python3

# Example to capture video for a specific duration starting at a specific time
# The start time and duration can be modified by changing "start_time" and "duration" variables
# The script will wait until the start time, start recording, and stop recording after the specified duration

import time
import threading
import logging
from datetime import datetime, timedelta
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
import re


# Define start_time and duration directly
start_time = datetime.strptime("08/09/2024 16:00", "%m/%d/%Y %H:%M")  # Example start time
duration = "1m"  # Example duration: 1 minute

# Format log file name based on start time
log_file_name = start_time.strftime("camera_status_%Y%m%d_%H%M.log")
video_file_name = start_time.strftime("video_%Y%m%d_%H%M.mp4")

# Configure logging
logging.basicConfig(filename=log_file_name, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# Function to log system status
def log_status(status):
    logging.info(f'Status: {status}')

# Parse the duration
length_match = re.match(r"(\d+)([hm])", duration)
if length_match:
    length_value = int(length_match.group(1))
    length_unit = length_match.group(2)
    if length_unit == 'h':
        length_seconds = length_value * 3600
    elif length_unit == 'm':
        length_seconds = length_value * 60
else:
    raise ValueError("Invalid duration format. Use '<number>h' for hours or '<number>m' for minutes.")

# Calculate the end time
end_time = start_time + timedelta(seconds=length_seconds)

# Function to start recording
def start_recording():
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration()
    picam2.configure(video_config)
    encoder = H264Encoder(10000000)
    output = FfmpegOutput(video_file_name)
    picam2.start()
    picam2.start_recording(encoder, output)
    log_status('Recording started')
    return picam2

# Function to stop recording
def stop_recording(picam2):
    picam2.stop_recording()
    picam2.stop()
    log_status('Recording stopped')

# Function to log recording progress periodically
def log_progress(end_time):
    while datetime.now() < end_time:
        time.sleep(300)  # Log every 5 minutes
        log_status('Recording in progress')

# Function to schedule the recording
def schedule_recording():
    now = datetime.now()
    time_to_start = (start_time - now).total_seconds()
    
    if time_to_start > 0:
        log_status(f'Waiting for {time_to_start} seconds before starting recording')
        time.sleep(time_to_start)
    
    # Start recording
    picam2 = start_recording()

    # Log recording progress periodically in a separate thread
    progress_thread = threading.Thread(target=log_progress, args=(end_time,))
    progress_thread.start()
    
    # Wait until the end time
    time_to_stop = (end_time - start_time).total_seconds()
    if time_to_stop > 0:
        log_status(f'Recording for {time_to_stop} seconds')
        time.sleep(time_to_stop)
    
    # Stop recording
    stop_recording(picam2)

    # Log that recording has completed and no further action
    log_status('Recording completed. No further action.')

# Run the scheduling function in a separate thread
thread = threading.Thread(target=schedule_recording)
thread.start()