#!/usr/bin/env python3
"""
huenit_laser.py
---------------
Engrave an SVG file on wood (or other material) with the Huenit laser attachment.

Usage:
    python3 huenit_laser.py design.svg
    python3 huenit_laser.py design.svg --size 60      # max dimension in mm (default 60)
    python3 huenit_laser.py design.svg --power 300    # laser power 0-1000 (default 500)
    python3 huenit_laser.py design.svg --speed 150    # engraving speed mm/min (default 200)
    python3 huenit_laser.py design.svg --focus 35     # Z height above material in mm (default 30)
    python3 huenit_laser.py design.svg --dry-run      # preview moves only, laser stays OFF

WARNING: Never look directly at the laser. Use protective goggles.
         Keep hands away from the work area during engraving.
         Ensure adequate ventilation when burning wood.

G-code used:
    M3 S{power}  — laser ON at power level (0-1000)
    M5           — laser OFF
    $32=1        — enable GRBL laser mode (laser fires only during G1 moves)
"""

import sys, os, re, math, time, threading, argparse, json
import xml.etree.ElementTree as ET
import serial

# ── Config ────────────────────────────────────────────────────────────────────
PORT          = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
BAUD          = 115200
TRAVEL_FEED   = 800    # mm/min while laser is off (travel between paths)
DEFAULT_FEED  = 200    # mm/min while engraving (slower = deeper burn)
DEFAULT_SIZE  = 60.0   # mm, max dimension (smaller than pen drawing for safety)
DEFAULT_POWER = 500    # 0-1000 laser power
DEFAULT_FOCUS = 30.0   # mm Z height above material (adjust to laser focal length)
CURVE_STEPS   = 20
CIRCLE_STEPS  = 48

OK_PAT = re.compile(rb"\bok\b", re.I)


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
        print(f"  ! timeout waiting for ok on: {line}")

    def wait_motion(self):
        self.send("M400", wait_ok=True, timeout=60.0)

    def close(self):
        try:
            self.ser.close()
        except:
            pass


# ── Bezier helpers (identical to huenit_svg.py) ───────────────────────────────
def cubic_bezier(p0, p1, p2, p3, steps):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0]
        y = u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


def quadratic_bezier(p0, p1, p2, steps):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**2*p0[0] + 2*u*t*p1[0] + t**2*p2[0]
        y = u**2*p0[1] + 2*u*t*p1[1] + t**2*p2[1]
        pts.append((x, y))
    return pts


# ── SVG path parser (identical to huenit_svg.py) ─────────────────────────────
def tokenize_path(d):
    return re.findall(
        r'[MmLlHhVvCcQqSsTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',
        d
    )


def parse_path_d(d):
    tokens = tokenize_path(d)
    segments = []
    i = 0
    cmd = None
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0
    last_ctrl = None

    def next_nums(n):
        nonlocal i
        result = []
        for _ in range(n):
            if i < len(tokens) and re.match(r'[-+]?(?:\d+\.?\d*|\.\d+)', tokens[i]):
                result.append(float(tokens[i]))
                i += 1
            else:
                result.append(0.0)
        return result

    while i < len(tokens):
        t = tokens[i]
        if re.match(r'[MmLlHhVvCcQqSsTtAaZz]', t):
            cmd = t
            i += 1
            last_ctrl = None

        if cmd is None:
            i += 1
            continue

        if cmd in ('M', 'm'):
            x, y = next_nums(2)
            if cmd == 'm': x += cx; y += cy
            segments.append(('move', x, y))
            sx, sy = x, y
            cx, cy = x, y
            cmd = 'L' if cmd == 'M' else 'l'

        elif cmd in ('L', 'l'):
            x, y = next_nums(2)
            if cmd == 'l': x += cx; y += cy
            segments.append(('line', x, y))
            cx, cy = x, y

        elif cmd in ('H', 'h'):
            x, = next_nums(1)
            if cmd == 'h': x += cx
            segments.append(('line', x, cy))
            cx = x

        elif cmd in ('V', 'v'):
            y, = next_nums(1)
            if cmd == 'v': y += cy
            segments.append(('line', cx, y))
            cy = y

        elif cmd in ('C', 'c'):
            x1, y1, x2, y2, x, y = next_nums(6)
            if cmd == 'c':
                x1 += cx; y1 += cy; x2 += cx; y2 += cy; x += cx; y += cy
            pts = cubic_bezier((cx, cy), (x1, y1), (x2, y2), (x, y), CURVE_STEPS)
            for px, py in pts[1:]:
                segments.append(('line', px, py))
            last_ctrl = (x2, y2)
            cx, cy = x, y

        elif cmd in ('S', 's'):
            x2, y2, x, y = next_nums(4)
            if cmd == 's': x2 += cx; y2 += cy; x += cx; y += cy
            x1 = 2*cx - last_ctrl[0] if last_ctrl else cx
            y1 = 2*cy - last_ctrl[1] if last_ctrl else cy
            pts = cubic_bezier((cx, cy), (x1, y1), (x2, y2), (x, y), CURVE_STEPS)
            for px, py in pts[1:]:
                segments.append(('line', px, py))
            last_ctrl = (x2, y2)
            cx, cy = x, y

        elif cmd in ('Q', 'q'):
            x1, y1, x, y = next_nums(4)
            if cmd == 'q': x1 += cx; y1 += cy; x += cx; y += cy
            pts = quadratic_bezier((cx, cy), (x1, y1), (x, y), CURVE_STEPS)
            for px, py in pts[1:]:
                segments.append(('line', px, py))
            last_ctrl = (x1, y1)
            cx, cy = x, y

        elif cmd in ('T', 't'):
            x, y = next_nums(2)
            if cmd == 't': x += cx; y += cy
            x1 = 2*cx - last_ctrl[0] if last_ctrl else cx
            y1 = 2*cy - last_ctrl[1] if last_ctrl else cy
            pts = quadratic_bezier((cx, cy), (x1, y1), (x, y), CURVE_STEPS)
            for px, py in pts[1:]:
                segments.append(('line', px, py))
            last_ctrl = (x1, y1)
            cx, cy = x, y

        elif cmd in ('A', 'a'):
            rx, ry, xrot, large, sweep, x, y = next_nums(7)
            if cmd == 'a': x += cx; y += cy
            segments.append(('line', x, y))
            cx, cy = x, y

        elif cmd in ('Z', 'z'):
            if abs(cx - sx) > 0.01 or abs(cy - sy) > 0.01:
                segments.append(('line', sx, sy))
            cx, cy = sx, sy
            cmd = None

    return segments


def circle_to_segments(cx, cy, r):
    segs = []
    for i in range(CIRCLE_STEPS + 1):
        angle = 2 * math.pi * i / CIRCLE_STEPS
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        segs.append(('move' if i == 0 else 'line', x, y))
    return segs


def ellipse_to_segments(cx, cy, rx, ry):
    segs = []
    for i in range(CIRCLE_STEPS + 1):
        angle = 2 * math.pi * i / CIRCLE_STEPS
        x = cx + rx * math.cos(angle)
        y = cy + ry * math.sin(angle)
        segs.append(('move' if i == 0 else 'line', x, y))
    return segs


def rect_to_segments(x, y, w, h):
    return [
        ('move', x,     y),
        ('line', x + w, y),
        ('line', x + w, y + h),
        ('line', x,     y + h),
        ('line', x,     y),
    ]


def polyline_to_segments(points_str, close=False):
    nums = [float(v) for v in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)', points_str)]
    pts = list(zip(nums[0::2], nums[1::2]))
    if not pts:
        return []
    segs = [('move', pts[0][0], pts[0][1])]
    for px, py in pts[1:]:
        segs.append(('line', px, py))
    if close and len(pts) > 1:
        segs.append(('line', pts[0][0], pts[0][1]))
    return segs


def parse_svg(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    all_segments = []
    count = {'path': 0, 'circle': 0, 'other': 0}

    for elem in root.iter():
        tag = elem.tag
        if '}' in tag:
            tag = tag.split('}', 1)[1]

        if tag == 'path':
            d = elem.get('d', '')
            if d:
                segs = parse_path_d(d)
                if segs:
                    all_segments.extend(segs)
                    count['path'] += 1
        elif tag == 'circle':
            cx = float(elem.get('cx', 0)); cy = float(elem.get('cy', 0))
            r  = float(elem.get('r',  0))
            if r > 0:
                all_segments.extend(circle_to_segments(cx, cy, r))
                count['circle'] += 1
        elif tag == 'ellipse':
            cx = float(elem.get('cx', 0)); cy = float(elem.get('cy', 0))
            rx = float(elem.get('rx', 0)); ry = float(elem.get('ry', 0))
            if rx > 0 and ry > 0:
                all_segments.extend(ellipse_to_segments(cx, cy, rx, ry))
                count['other'] += 1
        elif tag == 'rect':
            x = float(elem.get('x', 0)); y = float(elem.get('y', 0))
            w = float(elem.get('width', 0)); h = float(elem.get('height', 0))
            if w > 0 and h > 0:
                all_segments.extend(rect_to_segments(x, y, w, h))
                count['other'] += 1
        elif tag == 'line':
            x1 = float(elem.get('x1', 0)); y1 = float(elem.get('y1', 0))
            x2 = float(elem.get('x2', 0)); y2 = float(elem.get('y2', 0))
            all_segments.extend([('move', x1, y1), ('line', x2, y2)])
            count['other'] += 1
        elif tag == 'polyline':
            pts = elem.get('points', '')
            if pts:
                all_segments.extend(polyline_to_segments(pts, close=False))
                count['other'] += 1
        elif tag == 'polygon':
            pts = elem.get('points', '')
            if pts:
                all_segments.extend(polyline_to_segments(pts, close=True))
                count['other'] += 1

    total = count['path'] + count['circle'] + count['other']
    print(f"  Parsed {total} element(s): {count['path']} path(s), "
          f"{count['circle']} circle(s), {count['other']} other")
    return all_segments


def transform_segments(segments, size_mm):
    xs = [x for _, x, _ in segments]
    ys = [y for _, _, y in segments]
    if not xs:
        return []

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    w = x_max - x_min
    h = y_max - y_min

    if max(w, h) == 0:
        return []

    scale    = size_mm / max(w, h)
    x_center = (x_min + x_max) / 2
    y_center = (y_min + y_max) / 2

    result = []
    for kind, x, y in segments:
        arm_x =  (x - x_center) * scale
        arm_y = -(y - y_center) * scale
        result.append((kind, arm_x, arm_y))

    print(f"  SVG size: {w:.1f}x{h:.1f}px -> {w*scale:.1f}x{h*scale:.1f}mm "
          f"(scale {scale:.3f})")
    return result


# ── Laser engrave ─────────────────────────────────────────────────────────────
def engrave_segments(g, segments, power, engrave_feed, dry_run=False):
    """Execute segments as G-code with laser on/off instead of Z moves."""
    laser_on = False
    cur_x = 0.0
    cur_y = 0.0
    moves = 0
    lines = 0
    total = sum(1 for k, _, _ in segments if k == 'line')
    path_n = 0
    LOG_EVERY = 50

    for kind, x, y in segments:
        dx = x - cur_x
        dy = y - cur_y

        if kind == 'move':
            if laser_on:
                if not dry_run:
                    g.send("M5", wait_ok=True)       # laser OFF
                    g.wait_motion()
                laser_on = False
            if abs(dx) > 0.01 or abs(dy) > 0.01:
                if not dry_run:
                    g.send(f"G1 X{dx:.3f} Y{dy:.3f} F{TRAVEL_FEED}", wait_ok=True)
                    g.wait_motion()
            moves += 1
            path_n += 1
            print(f"  LASER OFF  path {path_n} -> X:{x:+.1f} Y:{y:+.1f}mm")

        elif kind == 'line':
            if not laser_on:
                if not dry_run:
                    g.send(f"M3 S{power}", wait_ok=True)  # laser ON
                    g.wait_motion()
                laser_on = True
                print(f"  LASER ON   line {lines+1}/{total} (power {power})")
            if abs(dx) > 0.01 or abs(dy) > 0.01:
                if not dry_run:
                    g.send(f"G1 X{dx:.3f} Y{dy:.3f} F{engrave_feed}", wait_ok=True)
                    g.wait_motion()
            lines += 1
            if lines % LOG_EVERY == 0:
                pct = lines / total * 100 if total else 0
                print(f"  ENGRAVING  {lines}/{total} ({pct:.0f}%) X:{x:+.1f} Y:{y:+.1f}mm")

        cur_x, cur_y = x, y

    # Laser off at end
    if laser_on:
        if not dry_run:
            g.send("M5", wait_ok=True)
            g.wait_motion()

    # Return to center
    dx = -cur_x
    dy = -cur_y
    if abs(dx) > 0.01 or abs(dy) > 0.01:
        if not dry_run:
            g.send(f"G1 X{dx:.3f} Y{dy:.3f} F{TRAVEL_FEED}", wait_ok=True)
            g.wait_motion()

    print(f"  {moves} travel moves, {lines} engrave moves")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Engrave an SVG with the Huenit laser attachment"
    )
    parser.add_argument("svg", help="Path to SVG file")
    parser.add_argument("--size",    type=float, default=DEFAULT_SIZE,
                        help=f"Max dimension in mm (default {DEFAULT_SIZE})")
    parser.add_argument("--power",   type=int,   default=DEFAULT_POWER,
                        help=f"Laser power 0-1000 (default {DEFAULT_POWER})")
    parser.add_argument("--speed",   type=float, default=DEFAULT_FEED,
                        help=f"Engraving speed mm/min (default {DEFAULT_FEED})")
    parser.add_argument("--focus",   type=float, default=DEFAULT_FOCUS,
                        help=f"Z height above material in mm (default {DEFAULT_FOCUS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and preview moves only — laser stays OFF")
    args = parser.parse_args()

    if not os.path.exists(args.svg):
        print(f"  SVG file not found: {args.svg}")
        sys.exit(1)

    if args.power < 0 or args.power > 1000:
        print("  Power must be 0-1000")
        sys.exit(1)

    print("=" * 60)
    print("  HUENIT LASER ENGRAVER")
    print(f"  File:   {os.path.basename(args.svg)}")
    print(f"  Size:   max {args.size}mm")
    print(f"  Power:  {args.power}/1000")
    print(f"  Speed:  {args.speed} mm/min")
    print(f"  Focus:  {args.focus}mm above material")
    print(f"  Port:   {PORT}")
    if args.dry_run:
        print("  MODE:   DRY RUN (laser will NOT fire)")
    else:
        print("  WARNING: Laser will fire. Wear goggles. Ensure ventilation.")
    print("=" * 60)

    if not args.dry_run:
        confirm = input("  Ready? Type YES to start: ").strip()
        if confirm != "YES":
            print("  Aborted.")
            sys.exit(0)

    segments = parse_svg(args.svg)
    if not segments:
        print("  No drawable elements found in SVG.")
        sys.exit(1)

    segments = transform_segments(segments, args.size)

    g = GCodeIO(PORT, BAUD)
    try:
        # Enable GRBL laser mode (laser fires only during G1 moves, not G0)
        if not args.dry_run:
            g.send("$32=1", wait_ok=True)

        g.send("M5", wait_ok=True)          # ensure laser starts OFF
        g.send("G21", wait_ok=True)         # mm units
        g.send("G91", wait_ok=True)         # relative positioning

        # Move to focus height
        if not args.dry_run:
            g.send(f"G1 Z{args.focus:.2f} F{TRAVEL_FEED}", wait_ok=True)
            g.wait_motion()

        engrave_segments(g, segments, args.power, args.speed, dry_run=args.dry_run)

        # Lower Z back down before closing
        if not args.dry_run:
            g.send(f"G1 Z{-args.focus:.2f} F{TRAVEL_FEED}", wait_ok=True)
            g.wait_motion()
            g.send("$32=0", wait_ok=True)   # restore normal mode

        print("\n  Done.")
    finally:
        g.send("M5", wait_ok=True)          # safety: ensure laser off
        g.send("G90", wait_ok=True)
        g.close()


if __name__ == "__main__":
    main()
