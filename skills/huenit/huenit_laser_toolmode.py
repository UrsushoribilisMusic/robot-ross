#!/usr/bin/env python3
"""
huenit_laser_toolmode.py
-------------------------
Tests the hypothesis that the arm must be switched to "Laser Tool Mode"
before the laser will fire, and that M1401 is that switch command.

Sequence:
  1. Query module status (M1402) — see what module is detected
  2. Send M1401 to switch tool mode to Laser
  3. Re-query status (M1402) — confirm mode changed
  4. Set laser power (M1403 P1023)
  5. Fire laser (M1403 with C=1 single pulse, then hold)

Usage:
    python skills\\huenit\\huenit_laser_toolmode.py
    python skills\\huenit\\huenit_laser_toolmode.py --weak   # low power "weak light" test
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

def send(ser, cmd, wait=1.2):
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

def show(label, lines):
    print(f"  {label}")
    for l in lines[:8]:
        print(f"    {l}")
    if len(lines) > 8:
        print(f"    ... ({len(lines)-8} more lines)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weak", action="store_true",
                        help="Use low power (P50) for a safe 'weak light' first test")
    args = parser.parse_args()

    power = 50 if args.weak else 1023

    print(f"\nConnecting to {PORT}...")
    ser = connect()
    print("Connected.\n")

    print("SAFETY: Laser module installed? Goggles on? Wood in place?")
    input("Press Enter to continue...\n")

    # Step 1: query current module status
    print("Step 1 — Query current module (M1402)")
    lines = send(ser, "M1402", wait=1.0)
    show("M1402 response:", lines)
    print()

    # Step 2: switch tool mode to Laser
    print("Step 2 — Switch tool mode to Laser (M1401)")
    print("  (listen for a relay click from the arm head)")
    lines = send(ser, "M1401", wait=1.5)
    show("M1401 response:", lines)
    print()

    # Step 3: re-query status — should show different module now
    print("Step 3 — Re-query module after mode switch (M1402)")
    lines = send(ser, "M1402", wait=1.0)
    show("M1402 response:", lines)
    print()

    # Step 4: set laser power
    print(f"Step 4 — Set laser power to {power} (M1403 P{power} U5 C120 K10)")
    lines = send(ser, f"M1403 P{power} U5 C120 K10", wait=1.0)
    show("M1403 response:", lines)
    print()

    # Step 5: fire
    print("Step 5 — FIRE (M1403 single pulse C=1)")
    print(f"  WATCH THE WOOD — firing at power {power} for 3 seconds...")
    if not args.weak:
        print("  SAFETY: Do not look at beam. Goggles on.")
    confirm = input("  Type YES to fire: ").strip()
    if confirm != "YES":
        ser.close()
        return

    lines = send(ser, f"M1403 P{power} U5 C1 K10", wait=3.0)
    show("fire response:", lines)
    print()

    saw = input("  Did you see laser / burn mark? (y/n): ").strip().lower()
    if saw == "y":
        print(f"\n  SUCCESS! Sequence: M1401 (mode switch) -> M1403 P{power} (fire)")
        print(f"  Use --weak for low-power beam spot during focus calibration.")
    else:
        print("\n  Still no laser. Likely causes:")
        print("  - Physical: dirty pogo pins on tool changer (clean with IPA + Q-tip)")
        print("  - Power: not using original Huenit adapter (laser needs more current)")
        print("  - Module defective")
        print("\n  Also try: power cycle the arm after swapping modules.")

    # Always turn off
    send(ser, "M1403 P0 U5 C1 K10", wait=0.5)
    ser.close()

if __name__ == "__main__":
    main()
