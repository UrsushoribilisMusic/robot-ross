#!/usr/bin/env python3
"""
huenit_laser_manual.py
-----------------------
Manual laser test — sends one command, holds for N seconds, then turns off.
Gives you time to watch the wood for a burn mark.

Usage:
    python skills\\huenit\\huenit_laser_manual.py
"""
import sys, os, time
try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed.  pip install pyserial")
    sys.exit(1)

PORT = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
BAUD = 115200

def send(ser, cmd, wait=1.0):
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode("ascii", "ignore"))
    ser.flush()
    time.sleep(wait)
    out = ser.read(ser.in_waiting or 1)
    txt = out.decode("ascii", "ignore").strip()
    lines = [l for l in txt.splitlines() if l.strip()]
    return lines

def connect():
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(2)
    ser.write(b"\r\n\r\n")
    time.sleep(0.5)
    ser.reset_input_buffer()
    return ser

def test(ser, on_cmd, off_cmd, hold=5):
    print(f"\n  Sending: {on_cmd}")
    lines = send(ser, on_cmd, wait=0.5)
    for l in lines[:5]:
        print(f"    {l}")
    print(f"  Holding {hold}s — watch the wood NOW...")
    time.sleep(hold)
    print(f"  Sending off: {off_cmd}")
    send(ser, off_cmd, wait=0.5)
    result = input("  Did you see a laser or burn mark? (y/n): ").strip().lower()
    return result == "y"

def main():
    print(f"\nConnecting to {PORT}...")
    ser = connect()
    print("Connected.\n")

    print("SAFETY: Wear goggles. Wood in place? Hands clear?")
    input("Press Enter when ready...")

    # Sequence of tests, most likely first
    tests = [
        # Theory: M1403 sets power, M1401 fires
        ("Set power then fire",
         ["M1403 P1023 U5 C120 K10", "M1401"],
         "M1401 A0"),

        # Theory: M1401 alone is a simple on/off toggle
        ("M1401 bare toggle",
         ["M1401"],
         "M1401"),

        # Theory: M1401 with value 1 = on, value 0 = off
        ("M1401 A1",
         ["M1401 A1"],
         "M1401 A0"),

        # Theory: M1403 with C=1 runs 1 pulse, maybe that fires it
        ("M1403 single pulse P1023 C1",
         ["M1403 P1023 U5 C1 K10"],
         "M1403 P0 U5 C1 K10"),
    ]

    for label, on_cmds, off_cmd in tests:
        print(f"\n{'='*50}")
        print(f"TEST: {label}")
        print(f"{'='*50}")

        # Send all setup commands, then hold on last
        for cmd in on_cmds[:-1]:
            print(f"  Setup: {cmd}")
            lines = send(ser, cmd, wait=0.5)
            for l in lines[:3]:
                print(f"    {l}")

        fired = test(ser, on_cmds[-1], off_cmd, hold=5)
        if fired:
            print(f"\n  *** LASER FOUND! Command sequence: {' -> '.join(on_cmds)} ***")
            break
        print("  No laser seen, trying next...")

    ser.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
