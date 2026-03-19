#!/usr/bin/env python3
"""
huenit_laser_probe.py
----------------------
Diagnostic + brute-force probe for Huenit laser module control.

Usage:
    python skills\\huenit\\huenit_laser_probe.py            # firmware info only
    python skills\\huenit\\huenit_laser_probe.py --fire     # brute-force laser commands
    python skills\\huenit\\huenit_laser_probe.py --fire --start 1400 --end 1420

Known:
    - Firmware: Marlin bugfix-2.0.x on FYSETC_E4
    - Standard M3/M5/M106 are NOT compiled in (unknown command)
    - Suction module uses M1400 A[0-1023]  (from Hackaday reverse engineering)
    - Laser module command unknown — this script finds it by trying M1400-M1420
"""
import sys, os, time, argparse
try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

PORT = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
BAUD = 115200
BURN_SECONDS = 1.5   # how long to fire each candidate before turning off


def connect(port=PORT, baud=BAUD):
    try:
        ser = serial.Serial(port, baud, timeout=2)
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    time.sleep(2)
    ser.write(b"\r\n\r\n")
    time.sleep(0.5)
    ser.reset_input_buffer()
    return ser


def send(ser, line, wait=0.8):
    """Send a command and return the response text."""
    ser.reset_input_buffer()
    ser.write((line.strip() + "\n").encode("ascii", "ignore"))
    ser.flush()
    time.sleep(wait)
    out = b""
    deadline = time.time() + wait
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            out += ser.read(n)
        time.sleep(0.05)
    return out.decode("ascii", "ignore").strip()


def firmware_info(ser):
    print("=" * 55)
    print("Firmware (M115)")
    print("=" * 55)
    r = send(ser, "M115", wait=2.0)
    for line in r.splitlines():
        if line.strip():
            print(f"  {line}")
    print()


def brute_force(ser, start, end):
    """
    Try every M-code from M{start} to M{end} with two power formats:
      A1023   (Huenit suction-style)
      S255    (Marlin spindle-style, just in case)

    For each: fire for BURN_SECONDS, then send the same command with A0/S0.
    Print response and whether it was "ok" or "unknown".
    Watch the arm — when the laser fires, note the command printed on screen.
    """
    print("=" * 55)
    print(f"Brute-force M{start} through M{end}")
    print(f"Each command fires for {BURN_SECONDS}s then turns off.")
    print("Watch the laser — note which command triggers it.")
    print("=" * 55)
    print()

    for code in range(start, end + 1):
        for fmt, off_fmt in [("A1023", "A0"), ("S255", "S0")]:
            on_cmd  = f"M{code} {fmt}"
            off_cmd = f"M{code} {off_fmt}"

            r_on = send(ser, on_cmd, wait=0.5)
            is_unknown = "Unknown" in r_on or "unknown" in r_on

            status = "UNKNOWN" if is_unknown else "OK <<<< CHECK LASER"
            print(f"  {on_cmd:20s}  →  {status}")
            if r_on and not is_unknown:
                for line in r_on.splitlines():
                    if line.strip():
                        print(f"               reply: {line}")

            if not is_unknown:
                # Command was accepted — hold laser on so user can see it
                time.sleep(BURN_SECONDS)

            # Always send off command
            send(ser, off_cmd, wait=0.3)
            time.sleep(0.2)

    print()
    print("Done. Any line that showed 'OK <<<< CHECK LASER' is a candidate.")
    print("If you saw the laser fire, note that M-code and report it.")


def main():
    parser = argparse.ArgumentParser(
        description="Huenit laser probe — find the laser M-code"
    )
    parser.add_argument("--fire",  action="store_true",
                        help="Run brute-force laser command search")
    parser.add_argument("--start", type=int, default=1400,
                        help="First M-code to try (default 1400)")
    parser.add_argument("--end",   type=int, default=1420,
                        help="Last M-code to try (default 1420)")
    args = parser.parse_args()

    print(f"\nConnecting to {PORT} at {BAUD} baud...")
    ser = connect()
    print("Connected.\n")

    firmware_info(ser)

    if not args.fire:
        print("Run with --fire to brute-force laser commands.")
        print(f"  python skills\\huenit\\huenit_laser_probe.py --fire")
        print(f"  python skills\\huenit\\huenit_laser_probe.py --fire --start 1400 --end 1430")
        ser.close()
        return

    print("SAFETY: The laser may fire during this scan.")
    print("        Wear goggles. Do not look at the beam.")
    print("        Keep hands clear of the work area.")
    confirm = input("\nType YES to start: ").strip()
    if confirm != "YES":
        print("Aborted.")
        ser.close()
        return

    print()
    brute_force(ser, args.start, args.end)
    ser.close()


if __name__ == "__main__":
    main()
