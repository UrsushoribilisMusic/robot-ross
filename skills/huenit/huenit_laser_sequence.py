#!/usr/bin/env python3
"""
huenit_laser_sequence.py
-------------------------
Tries the exact community-found handshake sequence:
  M1400 A0  -> T4 -> M1008 A3 -> M106 S25 -> M107

M1008 A3 is the new element — "wakes up" tool-head communication
which may unlock M106 for the laser PWM pin.

Usage:
    python skills\\huenit\\huenit_laser_sequence.py
"""
import sys, os, time
try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed.  pip install pyserial")
    sys.exit(1)

PORT = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
BAUD = 115200

def connect():
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(2)
    ser.write(b"\r\n\r\n")
    time.sleep(0.5)
    ser.reset_input_buffer()
    return ser

def send(ser, cmd, wait=2.0):
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode("ascii", "ignore"))
    ser.flush()
    t0 = time.time()
    out = b""
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            out += ser.read(n)
        time.sleep(0.05)
    lines = [l.strip() for l in out.decode("ascii", "ignore").splitlines() if l.strip()]
    return lines

def step(ser, cmd, label, wait=2.0):
    lines = send(ser, cmd, wait=wait)
    unknown = any("Unknown" in l or "Invalid" in l for l in lines)
    status = "UNKNOWN/INVALID" if unknown else "OK"
    print(f"  [{status}] {cmd}  — {label}")
    for l in lines[:4]:
        print(f"           {l}")
    print()
    return not unknown

def main():
    print(f"\nConnecting to {PORT}...")
    ser = connect()
    print("Connected.\n")

    print("Community handshake sequence: M1400 A0 -> T4 -> M1008 A3 -> M106 S25")
    print("SAFETY: Laser module installed? Goggles on? Wood in place?")
    confirm = input("Type YES to start: ").strip()
    if confirm != "YES":
        ser.close()
        return

    print()

    # Step 1
    step(ser, "M1400 A0", "force suction OFF (safety interlock)")

    # Step 2
    step(ser, "T4", "select tool slot 4 (laser)")

    # Step 3 — the new element
    step(ser, "M1008 A3", "query encoders / wake up tool-head comms")

    # Step 4 — fire
    print("  Firing M106 S25 — WATCH THE WOOD for 5 seconds...")
    lines = send(ser, "M106 S25", wait=0.5)
    unknown = any("Unknown" in l for l in lines)
    print(f"  [{'UNKNOWN' if unknown else 'OK <<< CHECK LASER'}] M106 S25")
    for l in lines[:3]:
        print(f"    {l}")
    print()

    if not unknown:
        time.sleep(5)
    else:
        # M106 still unknown — try a few fallback power levels just in case
        print("  M106 still unknown. Trying M106 S255 (full power)...")
        lines = send(ser, "M106 S255", wait=0.5)
        unknown2 = any("Unknown" in l for l in lines)
        print(f"  [{'UNKNOWN' if unknown2 else 'OK <<< CHECK LASER'}] M106 S255")
        for l in lines[:3]:
            print(f"    {l}")
        if not unknown2:
            time.sleep(5)

    # Step 5 — off
    step(ser, "M107", "laser/fan off")

    result = input("Did you see laser / burn mark? (y/n): ").strip().lower()
    if result == "y":
        print("\n  SUCCESS! Sequence: M1400 A0 -> T4 -> M1008 A3 -> M106 S{{power}}")
        print("  Will update laser scripts with correct command sequence.")
    else:
        print("\n  Conclusion: laser PWM pin is disabled in this firmware build.")
        print("  The MOSFET may also be physically burned out (floating TTL pin issue).")
        print("  Email info@huenit.com with your firmware UUID: cede2a2f-41a2-4748-9b12-c55c62f367ff")

    ser.close()

if __name__ == "__main__":
    main()
