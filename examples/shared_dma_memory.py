#!/usr/bin/python3

"""
Example showing how to use the picamera DMA heap for sharing memory between processes. We use a number of buffers just
because it makes this example easier.

Usage: run `python shared_dma_memory.py writer` then follow the instructions to run the reader in another thread.

Homework for experts:
- Use some IPC to let the client thread know the parent PID/fds, and when new frames are ready.
- Don't need multiple - use a single buffer, and keep track of positions etc. Maybe add a header to the buffer so the
    client knows what's in there etc.
- Locks if you want - though note that currently the reader can happily read while the writer overwrites it.
- Better checksumming etc.
- Check out the picamera code ... there are a few places where DMA heaps are read from with memmaps. You could update
    that so they go straight to your buffer first. (Is there a way to copy directly from one memmap to another without
    entering userspace i.e. CMA -> CMA? Not sure. That'd be cool.)
"""

import mmap
import os
import struct
import time
from ctypes import CDLL, c_int, c_long, c_uint, get_errno
from os import strerror

from picamera2.dma_heap import DmaHeap


def main_writer(args):
    size = int(args.frame_height * args.frame_width * 3 / 2)  # Approx size for 64-aligned YUV420 frame.
    print(f"Writing to {args.num_shards} buffers with name={args.name}* and size={size}")

    # Create our buffers:
    heap = DmaHeap()
    fds = [heap.alloc(f"{args.name}-{i}", size) for i in range(args.num_shards)]
    memms = [mmap.mmap(fd.get(), size, mmap.MAP_SHARED, mmap.PROT_WRITE) for fd in fds]

    # Print the pid/fds so user can pick them for reader.
    pid = os.getpid()
    fd = fds[0].get()
    print(f"Run the reader with `python shared_dma_memory.py reader {pid} {fd} {size}`")

    # Now write in a loop, switching between buffers
    idx = 0
    n = 0
    dt = 0
    next_report_time = time.monotonic() + 1
    while True:
        # Create new data (it runs faster if you always write the same thing, but generally you'll be writing new frames
        # etc.). Note we add a header/footer so we can check they both match on read (if not, we read partway through a
        # write).
        data = bytearray((idx % 255).to_bytes() * size)

        # Make time the header/footer so we can measure latency. NB: do it after the above data creation, which isn't
        # what we're profiling here.
        header_size = struct.calcsize("d")
        t0 = time.monotonic()
        b = struct.pack("d", t0)
        data[:header_size] = b
        data[-header_size:] = b
        memm = memms[idx % args.num_shards]
        memm.seek(0)
        memm.write(data)

        # Report:
        dt += time.monotonic() - t0
        n += 1
        if t0 > next_report_time:
            print(f"Write dt = {dt / n*1000:0.3f}ms")
            next_report_time += 1
            dt = 0
            n = 0

        # Sleep if needed:
        if args.sleep_ms > 0:
            time.sleep(args.sleep_ms / 1000)

        idx += 1


# Magic (from stackoverflow - forgot link sorry)
_syscall = CDLL(None, use_errno=True).syscall
_syscall.argtypes = [c_long]


def pidfd_getfd(pidfd, targetfd):
    fd = _syscall(
        438,  # system call number of pidfd_getfd
        c_int(pidfd),
        c_int(targetfd),
        c_uint(0),  # unused "flags" argument
    )
    if fd == -1:
        errno = get_errno()
        raise OSError(errno, strerror(errno))
    return fd


def main_reader(args):
    print(f"Reading {args.size} bytes from fd {args.fd} or pid {args.pid}")
    fd = pidfd_getfd(os.pidfd_open(args.pid), args.fd)
    memm = mmap.mmap(fd, args.size, mmap.MAP_SHARED, mmap.PROT_READ)
    read_dt = 0
    dt_from_when_written = 0
    checksum_failed = 0
    n_read = 0
    next_report_time = time.monotonic() + 1
    last_read_header = None
    while True:
        # Read header and only read fully if it's changed
        header_size = struct.calcsize("d")
        memm.seek(0)
        header = memm.read(header_size)
        if header == last_read_header:
            continue
        last_read_header = header

        # Read the whole lot and measure time:
        t0 = time.monotonic()
        memm.seek(0)
        data = memm.read(args.size)
        t1 = time.monotonic()
        read_dt += t1 - t0
        n_read += 1

        # Measure the time since when it first started writing (i.e. the header) to when we've finished reading (now)
        dt_from_when_written += t1 - struct.unpack("d", header)[0]

        # Check footer matches header - if not, it means we read while the writer was writing. Which won't kill anything
        # but is something you need to be aware can happen!
        footer = data[-header_size:]
        if header != footer:
            checksum_failed += 1

        # Report:
        if t0 > next_report_time:
            print(
                (
                    f"Read time {read_dt / n_read*1000:0.3f}ms"
                    f" with latency {dt_from_when_written/n_read*1000:0.3f}ms"
                    f" with {checksum_failed/n_read*100:0.1f}% checksum failures"
                )
            )
            next_report_time += 1
            read_dt = 0
            dt_from_when_written = 0
            checksum_failed = 0
            n_read = 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)
    sub = subparsers.add_parser("writer")
    sub.add_argument("--name", default="dma-example")
    sub.add_argument("--frame-height", type=int, default=1024)
    sub.add_argument("--frame-width", type=int, default=768)
    sub.add_argument("--num-shards", type=int, default=10)
    sub.add_argument("--sleep-ms", type=int, default=0)
    sub.set_defaults(func=main_writer)
    sub = subparsers.add_parser("reader")
    sub.add_argument("pid", type=int)
    sub.add_argument("fd", type=int)
    sub.add_argument("size", type=int)
    sub.set_defaults(func=main_reader)
    args = parser.parse_args()
    args.func(args)
