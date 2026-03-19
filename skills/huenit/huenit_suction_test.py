#!/usr/bin/env python3
"""
huenit_suction_test.py
-----------------------
Quick test to verify the suction module responds to M1400 commands.
Confirms serial link + module port are working before debugging laser.

Usage:
    python skills\\huenit\\huenit_suction_test.py
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
    return out.decode("ascii", "ignore").strip()

def main():
    print(f"\nConnecting to {PORT}...")
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(2)
    ser.write(b"\r\n\r\n")
    time.sleep(0.5)
    ser.reset_input_buffer()
    print("Connected.\n")

    print("Suction module test — M1400 A[0-1023]")
    print("Make sure the suction cup is attached and module is plugged in.\n")
    input("Press Enter to turn suction ON (full power)...")

    r = send(ser, "M1400 A1023", wait=0.5)
    print(f"  >> M1400 A1023")
    print(f"     {r}")
    print("  Suction should be ON now. Hold something under the cup.")

    input("\nPress Enter to turn suction OFF...")
    r = send(ser, "M1400 A0", wait=0.5)
    print(f"  >> M1400 A0")
    print(f"     {r}")
    print("  Suction should be OFF now.")

    worked = input("\nDid the suction work? (y/n): ").strip().lower()
    if worked == "y":
        print("\n  Serial link and module port are confirmed working.")
        print("  The laser module itself is likely the issue — wrong slot, defective, or different command range.")
    else:
        print("\n  Suction also not working. Possible causes:")
        print("  - Module not fully seated in the port")
        print("  - Wrong USB port / COM port")
        print("  - Module port on the arm may need a power cycle")

    ser.close()

if __name__ == "__main__":
    main()
