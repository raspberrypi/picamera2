#!/usr/bin/python3

# Test that the allocators don't leak

from picamera2 import Picamera2
from picamera2.allocators import DmaAllocator, LibcameraAllocator

for _ in range(20):
    picam2 = Picamera2()
    picam2.allocator = LibcameraAllocator(picam2.camera)
    picam2.configure("still")
    picam2.close()

for _ in range(20):
    picam2 = Picamera2()
    picam2.allocator = DmaAllocator()
    picam2.configure("still")
    picam2.close()
