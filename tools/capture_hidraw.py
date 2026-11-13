#!/usr/bin/env python3
"""Read raw HID reports from a hidraw node and print timestamped hex.

Usage: sudo ./capture_hidraw.py [/dev/hidraw0]
"""
import os, sys, time

path = sys.argv[1] if len(sys.argv) > 1 else "/dev/hidraw0"
fd = os.open(path, os.O_RDONLY)
print(f"Reading {path}. Ctrl-C to stop.", flush=True)
t0 = time.time()
try:
    while True:
        data = os.read(fd, 64)
        if not data:
            continue
        ts = time.time() - t0
        print(f"{ts:8.3f}  len={len(data):2d}  {data.hex(' ')}", flush=True)
except KeyboardInterrupt:
    pass
