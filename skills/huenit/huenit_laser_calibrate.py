#!/usr/bin/env python3
"""
huenit_laser_calibrate.py
--------------------------
Calibration and test script for the Huenit laser attachment.

Steps:
  1. verify  — connect, send $$ to read GRBL settings, confirm laser mode available
  2. home     — home the arm (G28)
  3. pointer  — fire laser at low power (no movement) to see the beam spot for focus
  4. test     — burn a small test pattern: cross + square (5x5 mm) to check focus + power
  5. focus    — move Z to a specified height so you can measure the focal distance
  6. dot      — single dot burn at current position (power test)

Usage:
    python skills\\huenit\\huenit_laser_calibrate.py verify
    python skills\\huenit\\huenit_laser_calibrate.py home
    python skills\\huenit\\huenit_laser_calibrate.py pointer --power 50 --focus 30
    python skills\\huenit\\huenit_laser_calibrate.py dot --power 200
    python skills\\huenit\\huenit_laser_calibrate.py test --power 300 --focus 30
    python skills\\huenit\\huenit_laser_calibrate.py test --dry-run

WARNING: Never look directly at the laser. Use protective goggles.
         Ensure ventilation — burning wood produces smoke.
"""

import sys, os, re, time, argparse, json

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
PORT          = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
BAUD          = 115200
DEFAULT_POWER = 300    # conservative default for first test
DEFAULT_FOCUS = 30.0   # mm — distance from laser head to material surface
POINTER_POWER = 40     # very low power just to see the beam spot (not to burn)
OK_PAT        = re.compile(rb"\bok\b", re.I)
ERR_PAT       = re.compile(rb"error", re.I)


# ── Serial helpers ─────────────────────────────────────────────────────────────
def open_port(port, baud=BAUD):
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)          # wait for GRBL to wake up
        ser.write(b"\r\n\r\n")
        time.sleep(0.5)
        ser.reset_input_buffer()
        return ser
    except serial.SerialException as e:
        print(f"  ERROR opening {port}: {e}")
        sys.exit(1)


def send_cmd(ser, line, timeout=10.0, verbose=True):
    cmd = (line.strip() + "\n").encode("ascii", "ignore")
    ser.write(cmd)
    ser.flush()
    if verbose:
        print(f"  >> {line.strip()}")
    t0 = time.time()
    reply_lines = []
    while time.time() - t0 < timeout:
        raw = ser.readline()
        if raw:
            txt = raw.decode("ascii", "ignore").strip()
            if txt:
                reply_lines.append(txt)
                if verbose:
                    print(f"     {txt}")
            if OK_PAT.search(raw) or ERR_PAT.search(raw):
                break
    return reply_lines


def wait_idle(ser, timeout=60.0):
    """Poll '?' until machine reports Idle."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        ser.write(b"?")
        ser.flush()
        time.sleep(0.1)
        raw = ser.read(ser.in_waiting or 1)
        txt = raw.decode("ascii", "ignore")
        if "Idle" in txt:
            return True
        time.sleep(0.3)
    return False


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_verify(args):
    """Connect and read GRBL settings to confirm laser mode is supported."""
    print(f"\nConnecting to {PORT} at {BAUD} baud...")
    ser = open_port(PORT)
    print("  Connected.\n")

    print("--- GRBL version ---")
    send_cmd(ser, "$I")

    print("\n--- Checking key settings ($$ output) ---")
    ser.write(b"$$\n")
    ser.flush()
    t0 = time.time()
    settings = {}
    while time.time() - t0 < 5.0:
        raw = ser.readline()
        if not raw:
            break
        txt = raw.decode("ascii", "ignore").strip()
        if txt:
            print(f"     {txt}")
            m = re.match(r'\$(\d+)=([^\s]+)', txt)
            if m:
                settings[int(m.group(1))] = m.group(2)
        if OK_PAT.search(raw):
            break

    print()
    laser_mode = settings.get(32, "?")
    if str(laser_mode) == "1":
        print("  [OK] $32=1 — Laser mode is ALREADY enabled.")
    else:
        print(f"  [--] $32={laser_mode} — Laser mode off. Will enable it before engraving.")

    print("\n  Verification complete. Arm is responding.")
    ser.close()


def cmd_home(args):
    """Send the arm home (G28 / homing cycle)."""
    print(f"\nHoming arm on {PORT}...")
    ser = open_port(PORT)
    send_cmd(ser, "$H", timeout=30.0)
    print("  Home complete.")
    ser.close()


def cmd_focus(args):
    """Move Z to the specified focus height so you can set the laser distance."""
    print(f"\nMoving Z to focus height {args.focus}mm on {PORT}...")
    ser = open_port(PORT)
    send_cmd(ser, "G21")             # mm units
    send_cmd(ser, "G90")             # absolute mode
    send_cmd(ser, f"G1 Z{args.focus:.2f} F300")
    send_cmd(ser, "M400")            # wait for motion
    print(f"\n  Z is now at {args.focus}mm.")
    print("  Place your material under the laser head.")
    print("  Adjust the laser module ring until the beam dot is smallest/sharpest.")
    ser.close()


def cmd_pointer(args):
    """Fire laser at very low power (no movement) — lets you see where the beam points."""
    print(f"\nLaser pointer mode — power {args.power}/1000, press Ctrl+C to stop.")
    if not args.dry_run:
        print("\n  SAFETY: The laser WILL fire. Wear goggles. Do not look at beam.")
        confirm = input("  Type YES to continue: ").strip()
        if confirm != "YES":
            print("  Aborted.")
            return

    ser = open_port(PORT)
    send_cmd(ser, "$32=1", verbose=False)   # laser mode
    send_cmd(ser, "G21")
    send_cmd(ser, "G90")
    send_cmd(ser, f"G1 Z{args.focus:.2f} F300")
    send_cmd(ser, "M400")

    if args.dry_run:
        print("  [DRY RUN] Would fire M3 S{args.power} now.")
    else:
        send_cmd(ser, f"M3 S{args.power}")
        print(f"\n  Laser ON at power {args.power}. Press Ctrl+C to turn off.")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    send_cmd(ser, "M5")
    send_cmd(ser, "$32=0")
    print("\n  Laser OFF.")
    ser.close()


def cmd_dot(args):
    """Burn a single dot at current position for power testing."""
    print(f"\nDot test — power {args.power}/1000, duration {args.duration}s at focus {args.focus}mm")
    if not args.dry_run:
        print("\n  SAFETY: The laser WILL fire briefly. Wear goggles.")
        confirm = input("  Type YES to continue: ").strip()
        if confirm != "YES":
            print("  Aborted.")
            return

    ser = open_port(PORT)
    send_cmd(ser, "$32=1", verbose=False)
    send_cmd(ser, "G21")
    send_cmd(ser, "G90")
    send_cmd(ser, f"G1 Z{args.focus:.2f} F300")
    send_cmd(ser, "M400")

    if args.dry_run:
        print(f"  [DRY RUN] Would fire M3 S{args.power} for {args.duration}s then M5.")
    else:
        send_cmd(ser, f"M3 S{args.power}")
        time.sleep(args.duration)
        send_cmd(ser, "M5")

    send_cmd(ser, "$32=0")
    print(f"\n  Done. Check dot burn depth — adjust --power and --duration as needed.")
    ser.close()


def cmd_test(args):
    """Burn a small calibration pattern: 5x5mm square + crosshair."""
    power = args.power
    focus = args.focus
    speed = args.speed
    dry   = args.dry_run

    print(f"\nLaser calibration test pattern")
    print(f"  Power:  {power}/1000")
    print(f"  Speed:  {speed} mm/min")
    print(f"  Focus:  {focus}mm")
    print(f"  Size:   5x5mm square + crosshair")
    if dry:
        print("  MODE:   DRY RUN (laser stays OFF)")
    else:
        print("\n  SAFETY: Laser WILL fire. Wear goggles. Ensure ventilation.")
        confirm = input("  Type YES to start: ").strip()
        if confirm != "YES":
            print("  Aborted.")
            return

    # Pattern coordinates (relative to 0,0):
    #   Crosshair: horizontal line (-2.5,0)→(2.5,0), vertical (0,-2.5)→(0,2.5)
    #   Square: (0,0)→(5,0)→(5,5)→(0,5)→(0,0)  [offset so pattern is 0..5 range]

    # We'll keep it centred: crosshair at 2.5,2.5 within a 5x5 box
    # Origin stays wherever the arm currently is
    G = []
    G.append("G21")          # mm
    G.append("G90")          # absolute
    G.append(f"G1 Z{focus:.2f} F300")
    if not dry:
        G.append("$32=1")

    def laser_on():
        return [] if dry else [f"M3 S{power}"]

    def laser_off():
        return [] if dry else ["M5"]

    def move(x, y):
        return [f"G1 X{x:.3f} Y{y:.3f} F{speed}"]

    def travel(x, y):
        return laser_off() + [f"G0 X{x:.3f} Y{y:.3f}"] + laser_on()

    # Crosshair
    G += travel(-2.5, 0.0)
    G += move(2.5, 0.0)          # horizontal
    G += travel(0.0, -2.5)
    G += move(0.0, 2.5)          # vertical
    G += laser_off()

    # Square
    G += travel(0.0, 0.0)
    G += laser_on()
    G += move(5.0, 0.0)
    G += move(5.0, 5.0)
    G += move(0.0, 5.0)
    G += move(0.0, 0.0)
    G += laser_off()

    # Return home
    G += ["M400", "G0 X0 Y0"]
    if not dry:
        G += ["$32=0"]

    if dry:
        print("\n  [DRY RUN] G-code that would be sent:")
        for line in G:
            print(f"    {line}")
        return

    ser = open_port(PORT)
    try:
        for line in G:
            send_cmd(ser, line)
        print("\n  Test pattern complete.")
        print("  Inspect the burn:")
        print("    - Sharp, even lines → focus distance is good")
        print("    - Wide/fuzzy lines  → adjust focus ring or --focus height")
        print("    - Too light         → increase --power or decrease --speed")
        print("    - Too deep          → decrease --power or increase --speed")
    finally:
        send_cmd(ser, "M5")
        if not dry:
            send_cmd(ser, "$32=0")
        ser.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Huenit laser calibration and test"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # verify
    sub.add_parser("verify", help="Connect and read GRBL settings")

    # home
    sub.add_parser("home", help="Home the arm (G28 homing cycle)")

    # focus
    p_focus = sub.add_parser("focus", help="Move Z to focus height for distance setting")
    p_focus.add_argument("--focus", type=float, default=DEFAULT_FOCUS,
                         help=f"Z height in mm (default {DEFAULT_FOCUS})")

    # pointer
    p_ptr = sub.add_parser("pointer", help="Fire laser at low power to see beam spot")
    p_ptr.add_argument("--power",   type=int,   default=POINTER_POWER,
                       help=f"Laser power 0-1000 (default {POINTER_POWER})")
    p_ptr.add_argument("--focus",   type=float, default=DEFAULT_FOCUS,
                       help=f"Z height in mm (default {DEFAULT_FOCUS})")
    p_ptr.add_argument("--dry-run", action="store_true", dest="dry_run")

    # dot
    p_dot = sub.add_parser("dot", help="Burn a single dot (power test)")
    p_dot.add_argument("--power",    type=int,   default=DEFAULT_POWER,
                       help=f"Laser power 0-1000 (default {DEFAULT_POWER})")
    p_dot.add_argument("--focus",    type=float, default=DEFAULT_FOCUS,
                       help=f"Z height in mm (default {DEFAULT_FOCUS})")
    p_dot.add_argument("--duration", type=float, default=0.5,
                       help="Burn duration in seconds (default 0.5)")
    p_dot.add_argument("--dry-run",  action="store_true", dest="dry_run")

    # test
    p_test = sub.add_parser("test", help="Burn 5x5mm square + crosshair pattern")
    p_test.add_argument("--power",   type=int,   default=DEFAULT_POWER,
                        help=f"Laser power 0-1000 (default {DEFAULT_POWER})")
    p_test.add_argument("--speed",   type=float, default=200,
                        help="Engraving speed mm/min (default 200)")
    p_test.add_argument("--focus",   type=float, default=DEFAULT_FOCUS,
                        help=f"Z height in mm (default {DEFAULT_FOCUS})")
    p_test.add_argument("--dry-run", action="store_true", dest="dry_run")

    args = parser.parse_args()

    dispatch = {
        "verify":  cmd_verify,
        "home":    cmd_home,
        "focus":   cmd_focus,
        "pointer": cmd_pointer,
        "dot":     cmd_dot,
        "test":    cmd_test,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
