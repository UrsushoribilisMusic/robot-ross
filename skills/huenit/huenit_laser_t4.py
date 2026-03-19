#!/usr/bin/env python3
"""
huenit_laser_t4.py
-------------------
Tests the T4 tool-select sequence from community research.

Sequence:
  1. M1400 A0   — explicitly turn off suction
  2. T4         — force-select laser tool slot
  3. M106 S25   — fan/tool PWM at 10% (laser may be on fan pin)
  4. (hold 5s)
  5. M107       — fan/laser off

Usage:
    python skills\\huenit\\huenit_laser_t4.py
    python skills\\huenit\\huenit_laser_t4.py --power 128   # 50% (0-255)
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

def send(ser, cmd, wait=1.5):
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

def show(cmd, lines):
    print(f"  >> {cmd}")
    for l in lines[:6]:
        print(f"     {l}")
    print()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--power", type=int, default=25,
                        help="M106 S value 0-255 (default 25 = 10%%)")
    args = parser.parse_args()

    print(f"\nConnecting to {PORT}...")
    ser = connect()
    print("Connected.\n")

    print("T4 tool-select + M106 laser test")
    print(f"  M106 power: S{args.power} ({args.power/255*100:.0f}%%)")
    print("\nSAFETY: Laser module installed? Goggles on? Wood in place?")
    confirm = input("Type YES to start: ").strip()
    if confirm != "YES":
        ser.close()
        return

    print()

    # Step 1: suction off
    lines = send(ser, "M1400 A0", wait=1.0)
    show("M1400 A0 (suction off)", lines)

    # Step 2: T4 tool select
    lines = send(ser, "T4", wait=1.5)
    show("T4 (force laser tool)", lines)

    # Step 3: also try M1401 after T4
    lines = send(ser, "M1401", wait=1.0)
    show("M1401 (laser mode)", lines)

    # Step 4: check module status
    lines = send(ser, "M1402", wait=1.0)
    show("M1402 (module status)", lines)

    # Step 5: M106 — fan/tool PWM
    print(f"  Firing M106 S{args.power} — WATCH THE WOOD for 5 seconds...")
    lines = send(ser, f"M106 S{args.power}", wait=0.5)
    show(f"M106 S{args.power}", lines)

    time.sleep(5)

    # Step 6: off
    lines = send(ser, "M107", wait=0.5)
    show("M107 (off)", lines)

    result = input("Did you see laser / burn mark? (y/n): ").strip().lower()

    if result == "y":
        print(f"\n  SUCCESS! T4 + M106 S{{power}} fires the laser.")
        print(f"  On = M106 S{{0-255}}, Off = M107")
    else:
        # Try without T4 — maybe M106 alone works after M1401
        print("\n  Trying M106 alone (without T4, just after M1401)...")
        send(ser, "M1401", wait=1.0)
        lines = send(ser, f"M106 S{args.power}", wait=0.5)
        show(f"M106 S{args.power} (no T4)", lines)
        time.sleep(5)
        send(ser, "M107", wait=0.5)
        result2 = input("  Did you see laser this time? (y/n): ").strip().lower()
        if result2 == "y":
            print(f"\n  SUCCESS! M1401 + M106 S{{power}} fires the laser.")
        else:
            print("\n  M106 still unknown or laser PWM truly disabled.")
            print("  Last resort: contact Huenit for firmware .bin with laser enabled.")

    ser.close()

if __name__ == "__main__":
    main()
