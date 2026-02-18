#!/usr/bin/env python3
"""Quick test — sends M117 text to the Huenit LCD screen."""
import serial
import time
import sys
import os

PORT = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
msg  = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello Robot Ross"

print(f"Sending to display: {msg!r}")
s = serial.Serial(PORT, 115200, timeout=2)
time.sleep(1.5)
s.write(f"M117 {msg}\n".encode())
s.flush()
time.sleep(1)
s.close()
print("Done — check the screen!")
