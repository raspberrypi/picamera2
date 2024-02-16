#!/usr/bin/python3

# Test that the allocators don't leak

from picamera2 import Picamera2
from picamera2.allocators import (DmaAllocator, LibcameraAllocator,
                                  PersistentAllocator)

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

for _ in range(20):
    picam2 = Picamera2()
    picam2.allocator = PersistentAllocator()
    picam2.allocator.buffer_key = "still"
    picam2.configure("still")
    picam2.allocator.buffer_key = "preview"
    picam2.configure("preview")
    picam2.close()
