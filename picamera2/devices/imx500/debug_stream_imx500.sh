#!/bin/bash

# For instructions on how to used this script, please refer to the
# Picamera2 file imx500_progress_bar.txt.

SOURCE="/sys/kernel/debug/imx500-fw:$1/fw_progress"

if [ ! -f "$SOURCE" ]; then
    echo "Error: $SOURCE not found" >&2
    exit 1
fi

exec cat "$SOURCE"
