#!/usr/bin/env python3
"""
huenit_laser_motion.py
-----------------------
Tests the theory that M1403 fires laser pulses synchronized to G1 movement.

Sequence:
  1. M1401       — switch to laser tool mode  (module 5 -> 8 confirmed)
  2. M1403 P{p}  — configure laser power/pulses
  3. G1 X20 F100 — move 20mm while laser pulses fire along the path

If correct, this burns a dotted line on the wood.

Usage:
    python skills\\huenit\\huenit_laser_motion.py
    python skills\\huenit\\huenit_laser_motion.py --power 300 --dist 20
    python skills\\huenit\\huenit_laser_motion.py --weak     # power 50
"""
import sys, os, time, argparse
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
    lines = [l for l in out.decode("ascii", "ignore").splitlines() if l.strip()]
    return lines

def show(label, lines, max_lines=6):
    print(f"  {label}")
    for l in lines[:max_lines]:
        print(f"    {l}")
    if len(lines) > max_lines:
        print(f"    ... ({len(lines)-max_lines} more)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--power", type=int, default=500,
                        help="Laser power 0-1023 (default 500)")
    parser.add_argument("--dist",  type=float, default=20.0,
                        help="Distance to move in mm (default 20)")
    parser.add_argument("--feed",  type=float, default=100.0,
                        help="Feed rate mm/min (default 100, slow = more burn)")
    parser.add_argument("--weak",  action="store_true",
                        help="Use power=50 for a safe first test")
    args = parser.parse_args()

    power = 50 if args.weak else args.power

    print(f"\nConnecting to {PORT}...")
    ser = connect()
    print("Connected.\n")

    print(f"Motion-sync laser test")
    print(f"  Power:    {power}/1023")
    print(f"  Distance: {args.dist}mm")
    print(f"  Feed:     {args.feed} mm/min")
    print(f"\nSAFETY: Laser module installed? Goggles on? Wood in place?")
    print(f"        The arm WILL MOVE {args.dist}mm during this test.")
    confirm = input("\nType YES to fire: ").strip()
    if confirm != "YES":
        ser.close()
        return

    # Step 1: switch to laser tool mode
    print("\nStep 1 — Switch to laser mode (M1401)")
    lines = send(ser, "M1401", wait=1.5)
    show("response:", lines)

    # Confirm mode switched
    lines = send(ser, "M1402", wait=1.0)
    module_id = ""
    for l in lines:
        if l.strip() and not l.strip().startswith("="):
            module_id = l.strip()
            break
    print(f"  Module status: {' | '.join(l.strip() for l in lines[:4] if l.strip())}")

    # Step 2: set up absolute positioning + mm units
    print("\nStep 2 — Set up motion (G21 G90)")
    send(ser, "G21", wait=0.5)   # mm
    send(ser, "G90", wait=0.5)   # absolute

    # Step 3: configure laser
    print(f"\nStep 3 — Configure laser (M1403 P{power} U5 C120 K10)")
    lines = send(ser, f"M1403 P{power} U5 C120 K10", wait=1.0)
    show("response:", lines)

    # Step 4: move (laser should fire synchronized to motion)
    print(f"\nStep 4 — Moving {args.dist}mm at {args.feed}mm/min (LASER FIRING NOW)...")
    lines = send(ser, f"G1 X{args.dist:.1f} F{args.feed:.0f}", wait=30.0)
    show("move response:", lines)

    # Step 5: wait for motion to complete
    send(ser, "M400", wait=10.0)

    result = input("\nDid you see a laser line or burn marks? (y/n): ").strip().lower()
    if result == "y":
        print(f"\n  SUCCESS! Laser fires during G1 movement.")
        print(f"  Command sequence: M1401 -> M1403 P{{power}} U5 C120 K10 -> G1")
        print(f"  Will update huenit_laser.py with correct Marlin commands.")
    else:
        print("\n  No laser during motion either.")
        print("  Conclusion: laser PWM pin is disabled in this firmware build.")
        print("  Options:")
        print("    1. Flash updated Huenit firmware (contact Huenit support)")
        print("    2. Flash generic Marlin 2.1 with laser enabled (voids warranty)")
        print("    3. Use arm for pen/SVG drawing only (fully working)")

    # Return home
    print("\nReturning to origin...")
    send(ser, "G1 X0 F500", wait=10.0)
    send(ser, "M400", wait=5.0)
    ser.close()

if __name__ == "__main__":
    main()
