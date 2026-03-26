#!/usr/bin/env python3
"""
huenit_draw.py
--------------
Draw basic shapes (square, triangle, circle) with the Huenit arm holding a pen.

Usage:
    python3 huenit_draw.py calibrate       # Interactive Z calibration
    python3 huenit_draw.py square [size]    # Draw a square (default 30mm)
    python3 huenit_draw.py triangle [size]  # Draw a triangle (default 30mm)
    python3 huenit_draw.py circle [radius]  # Draw a circle (default 15mm)

The drawing plane is X/Y. Z controls pen up/down.
Calibrate first to find your Z_DOWN (pen touches paper) and Z_UP (pen lifted).
"""

import sys, os, time, re, math, threading, json, tempfile
import serial
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────
PORT = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
BAUD = 115200
DRAW_FEED = 400       # mm/min while drawing (slow for pen quality)
TRAVEL_FEED = 800     # mm/min while pen is up (moving between shapes)
CIRCLE_SEGMENTS = 72  # line segments to approximate a circle

# Z heights — override via calibration file
Z_UP = 5.0            # mm above paper (pen lifted)
Z_DOWN = 0.0          # mm to lower from up position to touch paper
TILT_SLOPE = 0.0      # mm of Z correction per mm of Y travel (from tilt calibration)

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "calibration.json")
READY_FLAG = os.path.join(tempfile.gettempdir(), "huenit_ready.flag")

OK_PAT = re.compile(rb"\bok\b", re.I)


def check_ready():
    if not os.path.exists(READY_FLAG):
        print("  ❌ Robot not calibrated this session.")
        print("     Run:  python3 huenit_draw.py calibrate")
        sys.exit(1)


# ── Serial / G-code ──────────────────────────────────────────────────────────
class GCodeIO:
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.buf = bytearray()
        self.lock = threading.Lock()
        self._rx = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx.start()

    def _rx_loop(self):
        while self.ser.is_open:
            try:
                n = self.ser.in_waiting
                if n:
                    d = self.ser.read(n)
                    if d:
                        with self.lock:
                            self.buf.extend(d)
                else:
                    time.sleep(0.005)
            except:
                break

    def send(self, line, wait_ok=True, timeout=10.0):
        self.ser.write((line.strip() + "\n").encode("ascii", "ignore"))
        self.ser.flush()
        if not wait_ok:
            return
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(0.01)
            with self.lock:
                if OK_PAT.search(self.buf):
                    self.buf.clear()
                    return
        print(f"  ⚠ timeout waiting for ok on: {line}")

    def wait_motion(self):
        """Wait for all queued motion to complete."""
        self.send("M400", wait_ok=True, timeout=30.0)

    def close(self):
        try:
            self.ser.close()
        except:
            pass


# ── Pen control ───────────────────────────────────────────────────────────────
def pen_up(g):
    print("  ✏️  pen UP")
    g.send(f"G1 Z{Z_UP:.2f} F{TRAVEL_FEED}", wait_ok=True)
    g.wait_motion()


def pen_down(g):
    print("  ✏️  pen DOWN")
    g.send(f"G1 Z{-Z_UP:.2f} F{TRAVEL_FEED}", wait_ok=True)
    g.wait_motion()


def _z_comp(dy):
    """Z compensation string for a Y move of dy mm."""
    dz = TILT_SLOPE * dy
    return f" Z{dz:.3f}" if abs(dz) > 0.001 else ""


def move_to(g, x, y):
    """Relative travel move (pen should be up)."""
    g.send(f"G1 X{x:.3f} Y{y:.3f}{_z_comp(y)} F{TRAVEL_FEED}", wait_ok=True)
    g.wait_motion()


def draw_to(g, x, y):
    """Relative draw move (pen should be down)."""
    g.send(f"G1 X{x:.3f} Y{y:.3f}{_z_comp(y)} F{DRAW_FEED}", wait_ok=True)
    g.wait_motion()


# ── Shapes ────────────────────────────────────────────────────────────────────
def draw_square(g, size=30.0):
    print(f"\n🟥 Drawing square ({size}mm)")
    pen_down(g)
    draw_to(g, size, 0)
    draw_to(g, 0, size)
    draw_to(g, -size, 0)
    draw_to(g, 0, -size)
    pen_up(g)
    print("  ✅ Square done")


def draw_triangle(g, size=30.0):
    """Equilateral triangle."""
    print(f"\n🔺 Drawing triangle ({size}mm)")
    h = size * math.sqrt(3) / 2
    pen_down(g)
    draw_to(g, size, 0)           # base
    draw_to(g, -size/2, h)        # up to apex
    draw_to(g, -size/2, -h)       # back to start
    pen_up(g)
    print("  ✅ Triangle done")


def draw_circle(g, radius=15.0):
    """Circle approximated with line segments."""
    print(f"\n⭕ Drawing circle (r={radius}mm)")
    n = CIRCLE_SEGMENTS

    # Move to start of circle (right side: +radius in X from center)
    move_to(g, radius, 0)
    pen_down(g)

    # Trace the circle
    prev_x, prev_y = radius, 0.0
    for i in range(1, n + 1):
        angle = 2 * math.pi * i / n
        cx = radius * math.cos(angle)
        cy = radius * math.sin(angle)
        dx = cx - prev_x
        dy = cy - prev_y
        draw_to(g, dx, dy)
        prev_x, prev_y = cx, cy

    pen_up(g)
    # Move back to center
    move_to(g, -radius, 0)
    print("  ✅ Circle done")


# ── Calibration ───────────────────────────────────────────────────────────────
def calibrate(g):
    """
    Calibration — new flow:
      1. User manually positions pen TOUCHING the paper (pen is DOWN).
      2. Press ENTER to confirm.
      3. Enter desired travel height in mm (recommended 5-8mm).
      4. Arm lifts pen to that height. Confirm or retry.
    """
    print("\n🔧 Calibration Mode")
    print("Step 1: Jog the tip until it TOUCHES the surface.")
    print("  W = up 0.5mm  |  S = down 0.5mm  |  Enter = confirm touching  |  Q = abort")
    import msvcrt
    while True:
        ch = msvcrt.getch()
        if ch in (b'\r', b'\n'):
            break
        if ch.lower() == b'q':
            print("\n  ❌ Calibration aborted.")
            return
        if ch.lower() == b'w':
            g.send("G1 Z0.5 F100", wait_ok=True)
            g.wait_motion()
            print("  > Z +0.5mm")
        elif ch.lower() == b's':
            g.send("G1 Z-0.5 F100", wait_ok=True)
            g.wait_motion()
            print("  > Z -0.5mm")

    while True:
        try:
            raw = input("\nStep 2: Enter travel height in mm [recommended 5-8, default 6]: ").strip()
            z_up = float(raw) if raw else 6.0
            if z_up <= 0:
                print("  ⚠  Must be positive.")
                continue
        except ValueError:
            print("  ⚠  Please enter a number.")
            continue

        print(f"  ↑ Lifting pen {z_up:.1f}mm...")
        g.send(f"G1 Z{z_up:.2f} F{TRAVEL_FEED}", wait_ok=True)
        g.wait_motion()

        ans = input(f"  Pen is now {z_up:.1f}mm above paper. Does it clear the paper well? [y / enter new value / q=abort]: ").strip().lower()
        if ans in ('y', 'yes', ''):
            # ── Step 3: 3-point Y-tilt calibration ────────────────────────────
            TILT_D = 40.0
            tilt_slope = 0.0

            print(f"\nStep 3 (optional): 3-point Y-tilt calibration.")
            print(f"  Samples Y=0 (center), Y+{TILT_D:.0f}mm, Y-{TILT_D:.0f}mm.")
            tilt_ans = input("  Calibrate Y-tilt? [Enter=yes / n=skip]: ").strip().lower()

            if tilt_ans != 'n':

                def fine_touch(label):
                    """W/S fine jog (0.1mm) until touching. Returns total Z adjustment."""
                    print(f"\n  [{label}]  W=up 0.1mm | S=down 0.1mm | Enter=touching")
                    z_adj = 0.0
                    while True:
                        ch = msvcrt.getch()
                        if ch in (b'\r', b'\n'):
                            break
                        if ch.lower() == b'w':
                            g.send("G1 Z0.1 F50", wait_ok=True)
                            g.wait_motion()
                            z_adj += 0.1
                            print(f"    Z +0.1mm  (total: {z_adj:+.2f}mm)")
                        elif ch.lower() == b's':
                            g.send("G1 Z-0.1 F50", wait_ok=True)
                            g.wait_motion()
                            z_adj -= 0.1
                            print(f"    Z -0.1mm  (total: {z_adj:+.2f}mm)")
                    return z_adj

                # ── Point B: Y+40 ──────────────────────────────────────────────
                print(f"\n  Moving to Y+{TILT_D:.0f}mm...")
                g.send(f"G1 Y{TILT_D:.1f} F{TRAVEL_FEED}", wait_ok=True)
                g.wait_motion()
                print(f"  Tip is at travel height. Jog down slowly until touching.")
                z_adj_pos = fine_touch(f"Y+{TILT_D:.0f}mm")

                # Lift back to travel height (undo the jog-down)
                g.send(f"G1 Z{-z_adj_pos:.2f} F{TRAVEL_FEED}", wait_ok=True)
                g.wait_motion()
                print(f"\n  Moving to Y-{TILT_D:.0f}mm...")
                g.send(f"G1 Y{-TILT_D * 2:.1f} F{TRAVEL_FEED}", wait_ok=True)
                g.wait_motion()

                # ── Point C: Y-40 ──────────────────────────────────────────────
                print(f"  Tip is at travel height. Jog down slowly until touching.")
                z_adj_neg = fine_touch(f"Y-{TILT_D:.0f}mm")

                # Lift back to travel height (undo the jog-down)
                g.send(f"G1 Z{-z_adj_neg:.2f} F{TRAVEL_FEED}", wait_ok=True)
                g.wait_motion()
                print(f"\n  Returning to Y=0...")
                g.send(f"G1 Y{TILT_D:.1f} F{TRAVEL_FEED}", wait_ok=True)
                g.wait_motion()

                # ── Compute slope (least squares through origin) ───────────────
                # Points: (TILT_D, z_adj_pos), (-TILT_D, z_adj_neg)
                tilt_slope = (TILT_D * z_adj_pos + (-TILT_D) * z_adj_neg) / (2 * TILT_D ** 2)
                print(f"\n  Y+{TILT_D:.0f}mm adjustment: {z_adj_pos:+.2f}mm")
                print(f"  Y-{TILT_D:.0f}mm adjustment: {z_adj_neg:+.2f}mm")
                print(f"  Tilt slope: {tilt_slope:.5f} mm/mm  ({tilt_slope*10:.3f}mm per 10cm Y)")
                print(f"  Returned to start.")

            # ── Save all calibration ───────────────────────────────────────────
            cal = {
                "z_up":       round(z_up, 2),
                "tilt_slope": round(tilt_slope, 5),
                "note":       "z_up = pen travel height mm; tilt_slope = Z mm per Y mm"
            }
            with open(CALIBRATION_FILE, "w") as f:
                json.dump(cal, f, indent=2)
            with open(READY_FLAG, "w") as f:
                f.write(f"calibrated z_up={z_up:.2f} tilt={tilt_slope:.5f}\n")
            print(f"\n  ✅ Saved! Z_UP={z_up:.1f}mm  tilt={tilt_slope:.5f} mm/mm — pen is UP and ready.")
            return
        elif ans == 'q':
            # Return pen to paper
            g.send(f"G1 Z{-z_up:.2f} F{TRAVEL_FEED}", wait_ok=True)
            g.wait_motion()
            print("  ❌ Calibration aborted — pen returned to paper.")
            return
        else:
            # User typed a new value — go back down to paper first, then retry
            g.send(f"G1 Z{-z_up:.2f} F{TRAVEL_FEED}", wait_ok=True)
            g.wait_motion()
            try:
                z_up = float(ans)
            except ValueError:
                pass  # will re-prompt


def load_calibration():
    global Z_UP, TILT_SLOPE
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE) as f:
            cal = json.load(f)
        Z_UP        = cal.get("z_up", Z_UP)
        TILT_SLOPE  = cal.get("tilt_slope", 0.0)
        tilt_info   = f", tilt={TILT_SLOPE:.4f} mm/mm" if TILT_SLOPE != 0 else ", no tilt"
        print(f"  📐 Loaded calibration: Z_UP = {Z_UP:.1f}mm{tilt_info}")
    else:
        print(f"  📐 No calibration file — using default Z_UP = {Z_UP:.1f}mm")
        print(f"     Run 'python3 huenit_draw.py calibrate' to calibrate.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 huenit_draw.py <command> [size]")
        print("  calibrate           Interactive pen-down calibration")
        print("  square [size_mm]    Draw a square (default 30)")
        print("  triangle [size_mm]  Draw a triangle (default 30)")
        print("  circle [radius_mm]  Draw a circle (default 15)")
        print("  demo                Draw all three shapes in a row")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    size = float(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"HUENIT Draw — Port: {PORT}")

    g = GCodeIO(PORT, BAUD)
    try:
        g.send("G21", wait_ok=True)  # metric
        g.send("G91", wait_ok=True)  # relative

        if cmd == "calibrate":
            calibrate(g)
            return

        check_ready()
        load_calibration()

        if cmd == "square":
            s = size or 30.0
            move_to(g, -s / 2, -s / 2)          # center: shift to bottom-left corner
            draw_square(g, s)                     # ends back at bottom-left corner, pen up
            move_to(g, s / 2, s / 2)             # return to original center
            print("\n  ✅ Done! (pen is up — safe to remove paper)")

        elif cmd == "triangle":
            s = size or 30.0
            move_to(g, -s / 2, 0)               # center horizontally (base centered)
            draw_triangle(g, s)                   # ends back at base-left, pen up
            move_to(g, s / 2, 0)                # return to original center
            print("\n  ✅ Done! (pen is up — safe to remove paper)")

        elif cmd == "circle":
            draw_circle(g, size or 15.0)          # already centered around start point, pen up
            print("\n  ✅ Done! (pen is up — safe to remove paper)")

        elif cmd == "demo":
            s = size or 25.0
            # Square (centered)
            move_to(g, -s / 2, -s / 2)
            draw_square(g, s)
            move_to(g, s / 2 + 35, s / 2)       # back to center then right to next shape
            # Triangle (centered)
            move_to(g, -s / 2, 0)
            draw_triangle(g, s)
            move_to(g, s / 2 + 35, 0)           # back to center then right to next shape
            # Circle (already centered)
            r = size or 12.0
            draw_circle(g, r)
            # Return to original start
            move_to(g, -(70 + r), 0)
            print("\n🎨 Demo complete! (pen is up — safe to remove paper)")

        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)

    finally:
        g.send("G90", wait_ok=True)
        g.close()


if __name__ == "__main__":
    main()
