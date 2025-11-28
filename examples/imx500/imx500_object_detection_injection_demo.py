import argparse
import glob
import io
import os
import sys
import time
from contextlib import closing
from functools import lru_cache

import cv2
import numpy as np
import OpenEXR
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow

from picamera2 import Picamera2
from picamera2.devices import IMX500
from picamera2.devices.imx500 import (NetworkIntrinsics,
                                      postprocess_nanodet_detection)

tensor_files = []
current_tensor_index = 0
current_injection_cmp_frm = None  # Store the current injection comparison frame
tensor_pause_duration = 0.1  # Configurable pause after tensor verification
tensor_verified_time = None  # Timestamp when tensor was last verified as matching
first_tensor_injected = False  # Flag to track if first tensor has been injected
saved_tensors = set()  # Track already saved tensor files to avoid duplicates


def process_and_display_tensor(input_tensor, frame_count, metadata):
    # Parse detections
    detections = parse_detections(metadata)

    # Convert input tensor to image
    tensor_image = imx500.input_tensor_image(input_tensor)

    # Do all expensive OpenCV operations here
    h, w = tensor_image.shape[:2]
    scale_factor = window.scale_factor

    # Scale up the image using OpenCV for better quality
    scaled_image = cv2.resize(
        tensor_image,
        (w * scale_factor, h * scale_factor),
        interpolation=cv2.INTER_LINEAR,
    )

    # Draw detections on the scaled image at the proper scale
    draw_detections(scaled_image, detections, scale_factor=scale_factor)

    # Convert BGR to RGB (final expensive operation)
    rgb_image = cv2.cvtColor(scaled_image, cv2.COLOR_BGR2RGB)

    # Update display immediately
    window.update_display_immediate(rgb_image)


def convert_and_inject_tensor(exr_path):
    """Convert EXR to tensor and inject it directly."""
    with closing(OpenEXR.InputFile(exr_path)) as exr_file:
        tensor_data = imx500.prepare_tensor_for_injection(exr_file)

    if not tensor_data:
        print(f"Failed to convert tensor: {os.path.basename(exr_path)}")
        return None

    try:
        memfd = os.memfd_create("tensor_data", os.MFD_CLOEXEC)
    except OSError as e:
        print(f"Failed to create memfd: {e}")
        return None

    try:
        with io.FileIO(memfd, "wb", closefd=False) as file_obj:
            with io.BufferedWriter(file_obj) as writer:
                writer.write(tensor_data)
                writer.flush()

        imx500._IMX500__set_input_tensor(memfd)
        return imx500.get_injection_cmp_frm()
    except Exception as e:
        print(f"Error setting tensor: {e}")
        raise
    finally:
        try:
            os.close(memfd)
        except OSError:
            pass


def load_specific_tensor(target_index):
    """Load a specific tensor by index."""
    if not tensor_files or target_index < 0 or target_index >= len(tensor_files):
        return False

    global current_tensor_index, current_injection_cmp_frm
    if not tensor_files or target_index < 0 or target_index >= len(tensor_files):
        return False

    exr_path = tensor_files[target_index]
    print(
        f"Loading tensor {target_index + 1}/{len(tensor_files)}: {os.path.basename(exr_path)}"
    )

    try:
        injection_cmp_frm = convert_and_inject_tensor(exr_path)
        if injection_cmp_frm is not None:
            current_tensor_index = target_index
            # Store the injection comparison frame globally
            current_injection_cmp_frm = injection_cmp_frm
            return True
        else:
            print(f"Failed to convert tensor: {os.path.basename(exr_path)}")
            return False

    except Exception as e:
        print(f"Error loading tensor: {e}")
        print("Tensor injection failed - exiting application")
        # Exit application on tensor loading failure
        import sys

        sys.exit(1)


def cycle_to_next_tensor():
    """Cycle to the next tensor file and set it on the IMX500."""
    # Don't cycle during startup phase
    if not first_tensor_injected:
        print("Cannot cycle tensors during startup phase")
        return

    if not tensor_files:
        print("No tensor files available")
        return

    # Calculate next index
    next_index = current_tensor_index + 1
    if next_index >= len(tensor_files):
        print("No more tensor files available")
        sys.exit(0)
    load_specific_tensor(next_index)


def save_output_tensor(output_tensor):
    """Save the output tensor data using the basename of the current EXR file with .out extension."""
    if not tensor_files or current_tensor_index >= len(tensor_files):
        print("Warning: No tensor files available for output naming")
        return

    # Get the current EXR file path and create output filename
    current_exr_path = tensor_files[current_tensor_index]
    base_name = os.path.splitext(os.path.basename(current_exr_path))[0]
    output_dir = os.path.dirname(current_exr_path)
    output_path = os.path.join(output_dir, f"{base_name}.out")

    # Check if we've already saved this tensor
    if output_path in saved_tensors:
        return  # Skip saving if already done

    try:
        # Convert output tensor to numpy array
        np_output = np.fromiter(output_tensor, dtype=np.float32)

        # Save as binary file
        np_output.tofile(output_path)
        print(f"Saved output tensor to: {output_path}")

        # Mark this tensor as saved
        saved_tensors.add(output_path)

    except Exception as e:
        print(f"Error saving output tensor: {e}")


def auto_cycle_timer_callback():
    """Timer callback that only cycles if not paused and ready."""
    global tensor_verified_time

    # Don't cycle during startup phase
    if not first_tensor_injected:
        return

    if tensor_verified_time is not None:
        elapsed = time.time() - tensor_verified_time
        if elapsed >= tensor_pause_duration:
            cycle_to_next_tensor()
            tensor_verified_time = None  # Reset for next cycle


class InputTensorWindow(QMainWindow):
    def __init__(self, scale_factor=3):
        super().__init__()
        self.setWindowTitle("Input Tensor Display - Esc: Exit")
        self.label = QLabel()
        self.setCentralWidget(self.label)
        self.scale_factor = scale_factor
        self.resize(
            320 * scale_factor, 320 * scale_factor
        )  # Default size, will be updated based on tensor size

        # Set up timer for tensor cycling with configurable interval
        self.tensor_timer = QTimer()
        self.tensor_timer.timeout.connect(auto_cycle_timer_callback)

        # Configure tensor cycling timer - always check frequently for state changes
        self.tensor_timer.start(100)  # Check every 100ms

        # Enable keyboard focus
        self.setFocusPolicy(Qt.StrongFocus)

    def update_display_immediate(self, rgb_image):
        """Update the display immediately with fully processed RGB image (main thread only)."""
        if rgb_image is None:
            return

        # Image is already scaled, processed, and in RGB format
        scaled_h, scaled_w, ch = rgb_image.shape
        bytes_per_line = ch * scaled_w

        # Create QImage (only remaining operation)
        qt_image = QImage(
            rgb_image.data, scaled_w, scaled_h, bytes_per_line, QImage.Format_RGB888
        )

        # Convert to QPixmap
        pixmap = QPixmap.fromImage(qt_image)
        self.label.setPixmap(pixmap)

        # Resize window to match scaled image size
        self.resize(scaled_w, scaled_h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            # Close the application
            self.close()
        else:
            # Pass other key events to parent
            super().keyPressEvent(event)

        event.accept()


class Detection:
    def __init__(self, coords, category, conf, metadata):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        # Convert inference coordinates to ISP output coordinates (x, y, w, h)
        converted_coords = imx500.convert_inference_coords(coords, metadata, picam2)

        # Scale from ISP output coordinates to input tensor coordinates
        isp_w, isp_h = picam2.camera_configuration()["main"]["size"]
        input_w, input_h = imx500.get_input_size()

        x, y, w, h = converted_coords
        # Scale coordinates from ISP size to input tensor size
        scale_x = input_w / isp_w
        scale_y = input_h / isp_h

        self.box = (
            int(x * scale_x),
            int(y * scale_y),
            int(w * scale_x),
            int(h * scale_y),
        )


def parse_detections(metadata: dict):
    """Parse the output tensor into a number of detected objects, scaled to the ISP output."""
    bbox_normalization = intrinsics.bbox_normalization
    bbox_order = intrinsics.bbox_order
    threshold = args.threshold
    iou = args.iou
    max_detections = args.max_detections

    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    input_w, input_h = imx500.get_input_size()
    if np_outputs is None:
        return []
    if intrinsics.postprocess == "nanodet":
        boxes, scores, classes = postprocess_nanodet_detection(
            outputs=np_outputs[0],
            conf=threshold,
            iou_thres=iou,
            max_out_dets=max_detections,
        )[0]
        from picamera2.devices.imx500.postprocess import scale_boxes

        boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False, False)
    else:
        boxes, scores, classes = np_outputs[0][0], np_outputs[1][0], np_outputs[2][0]
        if bbox_normalization:
            boxes = boxes / input_h

        if bbox_order == "xy":
            boxes = boxes[:, [1, 0, 3, 2]]
        boxes = np.array_split(boxes, 4, axis=1)
        boxes = zip(*boxes)

    detections = []
    for box, score, category in zip(boxes, scores, classes):
        if score > threshold:
            detections.append(Detection(box, category, score, metadata))

    return detections


@lru_cache
def get_labels():
    labels = intrinsics.labels

    if intrinsics.ignore_dash_labels:
        labels = [label for label in labels if label and label != "-"]
    return labels


def draw_detections(image, detections, scale_factor=1):
    """Draw the detections onto the provided image."""
    if detections is None:
        return
    labels = get_labels()

    for detection in detections:
        # Coordinates are now in (x, y, w, h) format, already scaled to input tensor
        x, y, w, h = detection.box

        # Scale coordinates by the scale factor for display
        x = int(x * scale_factor)
        y = int(y * scale_factor)
        w = int(w * scale_factor)
        h = int(h * scale_factor)

        label = f"{labels[int(detection.category)]} ({detection.conf:.2f})"

        # Calculate text size and position (scale font size with scale_factor)
        font_scale = 0.5 * scale_factor
        thickness = max(1, int(scale_factor))
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        text_x = x + int(5 * scale_factor)
        text_y = y + int(15 * scale_factor)

        # Create a copy of the image to draw the background with opacity
        overlay = image.copy()

        # Draw the background rectangle on the overlay
        cv2.rectangle(
            overlay,
            (text_x, text_y - text_height),
            (text_x + text_width, text_y + baseline),
            (255, 255, 255),  # Background color (white)
            cv2.FILLED,
        )

        alpha = 0.30
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

        # Draw text on top of the background
        cv2.putText(
            image,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 0, 255),
            thickness,
        )

        # Draw detection box
        cv2.rectangle(
            image,
            (x, y),
            (x + w, y + h),
            (0, 255, 0, 0),
            thickness=max(2, int(2 * scale_factor)),
        )


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=str,
        help="Path of the model",
        default="/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk",
    )
    parser.add_argument("--fps", type=int, help="Frames per second")
    parser.add_argument(
        "--bbox-normalization",
        action=argparse.BooleanOptionalAction,
        help="Normalize bbox",
    )
    parser.add_argument(
        "--bbox-order",
        choices=["yx", "xy"],
        default="yx",
        help="Set bbox order yx -> (y0, x0, y1, x1) xy -> (x0, y0, x1, y1)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.55, help="Detection threshold"
    )
    parser.add_argument("--iou", type=float, default=0.65, help="Set iou threshold")
    parser.add_argument(
        "--max-detections", type=int, default=10, help="Set max detections"
    )
    parser.add_argument(
        "--ignore-dash-labels",
        action=argparse.BooleanOptionalAction,
        help="Remove '-' labels ",
    )
    parser.add_argument(
        "--postprocess",
        choices=["", "nanodet"],
        default=None,
        help="Run post process of type",
    )
    parser.add_argument(
        "-r",
        "--preserve-aspect-ratio",
        action=argparse.BooleanOptionalAction,
        help="preserve the pixel aspect ratio of the input tensor",
    )
    parser.add_argument("--labels", type=str, help="Path to the labels file")
    parser.add_argument(
        "--print-intrinsics",
        action="store_true",
        help="Print JSON network_intrinsics then exit",
    )
    parser.add_argument(
        "--tensor-dir",
        type=str,
        required=True,
        help="Directory containing EXR tensor files to step through",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()

    # This must be called before instantiation of Picamera2
    imx500 = IMX500(args.model, tensor_injection=True)
    intrinsics = imx500.network_intrinsics
    if not intrinsics:
        intrinsics = NetworkIntrinsics()
        intrinsics.task = "object detection"
    elif intrinsics.task != "object detection":
        print("Network is not an object detection task", file=sys.stderr)
        exit()

    # Override intrinsics from args
    for key, value in vars(args).items():
        if key == "labels" and value is not None:
            with open(value, "r") as f:
                intrinsics.labels = f.read().splitlines()
        elif hasattr(intrinsics, key) and value is not None:
            setattr(intrinsics, key, value)

    # Defaults
    if intrinsics.labels is None:
        with open("assets/coco_labels.txt", "r") as f:
            intrinsics.labels = f.read().splitlines()
    intrinsics.update_with_defaults()

    if args.print_intrinsics:
        print(intrinsics)
        exit()

    picam2 = Picamera2(imx500.camera_num)
    config = picam2.create_preview_configuration(
        controls={"FrameRate": 12, "CnnEnableInputTensor": True}, buffer_count=30
    )

    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=False)

    if intrinsics.preserve_aspect_ratio:
        imx500.set_auto_aspect_ratio()

    tensor_pattern = os.path.join(args.tensor_dir, "*.exr")
    found_files = sorted(glob.glob(tensor_pattern))

    if not found_files:
        print(f"No EXR files found in directory: {args.tensor_dir}")
        sys.exit(1)

    tensor_files = found_files  # Set global variable
    print(f"Found {len(tensor_files)} EXR tensor files")

    # Create Qt application and window
    app = QApplication(sys.argv)
    window = InputTensorWindow()
    window.show()

    def process_frame_metadata(request):
        """Process frame metadata and queue display work if frame matches injection comparison frame."""
        global first_tensor_injected, current_injection_cmp_frm, tensor_verified_time

        # Inject first tensor if not done yet
        if not first_tensor_injected and tensor_files:
            first_tensor_injected = True
            load_specific_tensor(0)
            return  # Skip processing this frame to allow tensor injection to take effect

        md = request.get_metadata()

        # Print frameCount from output tensor info if available
        frame_count = None
        output_tensor_info = md.get("CnnOutputTensorInfo")
        if output_tensor_info:
            try:
                tensor_info = imx500._IMX500__get_output_tensor_info(output_tensor_info)
                frame_count = tensor_info.get("frameCount", "N/A")
            except Exception as e:
                print(f"Error getting frameCount from output tensor info: {e}")
                raise

        if current_injection_cmp_frm is not None and frame_count is not None:
            diff = (frame_count - current_injection_cmp_frm) & 0xFF
            if diff > (0xFF // 2):
                diff -= 0xFF + 1

            if diff == 0:
                current_injection_cmp_frm = None

                # Pause mode - start the delay timer
                tensor_verified_time = time.time()
            elif diff > 0:
                # Re-inject the current tensor
                load_specific_tensor(current_tensor_index)
                return
            else:
                return

        if "CnnOutputTensor" in md:
            save_output_tensor(md["CnnOutputTensor"])

        if "CnnInputTensor" in md:
            input_tensor = md["CnnInputTensor"]
            if imx500.config["input_tensor_size"] != (0, 0):
                process_and_display_tensor(input_tensor, frame_count, md)

    # Set the pre_callback to process frame metadata for each frame
    picam2.pre_callback = process_frame_metadata

    # Start Qt event loop
    try:
        app.exec_()
    finally:
        # No background threads to clean up in synchronous mode
        print("Application shutting down...")
