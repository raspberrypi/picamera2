# Real-time Object Detection on Raspberry Pi 4

## Requirements

- Raspberry Pi 4 with Raspberry Pi OS (64-bit)
- Python 3.11

## Dependencies

Before running the code, make sure to install the following dependencies:

```bash
sudo rm /usr/lib/python3.11/EXTERNALLY-MANAGED
sudo pip3 install opencv-python==4.8.1.78
sudo pip3 install mediapipe==0.10.8
```
## TensorFlow Lite Model with Metadata Format

This example uses a TensorFlow Lite model with metadata format. To convert your model to metadata format, follow these steps:

Prepare a text file containing the labels for your model.
Obtain the TFLite model.
Use the following Colab file to convert your model to metadata format:
<a href="https://colab.research.google.com/github/tensorflow/tensorflow/blob/master/tensorflow/lite/g3doc/models/convert/metadata_writer_tutorial.ipynb">Convert to Metadata Format - Colab File </a>

# Running the Code

To launch the code, execute the following commands:
```bash
# Navigate to the project directory
cd path/to/picamera2/real-time-object-detection-rpi4

# Run the real-time detection script
python3 real_time_detection_with_labels_on_raspberry4.py

```
<blockquote> 
<p dir="auto">Make sure to replace path/to/picamera2/ with the actual path to your picamera2 repository.</p>
<blockquote>