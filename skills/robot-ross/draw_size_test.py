#!/usr/bin/env python3
"""
draw_size_test.py
-----------------
Draws concentric squares at 100, 120, 140, 160, 180mm, each with its
size written in small text at the bottom-right corner.

Centering strategy:
  1. Draw square (ends at bottom-left corner).
  2. Return to center with a trivially simple move (+s/2, +s/2) — no label math.
  3. Touch paper (marks center dot), re-stamp G92 X0 Y0 at confirmed center.
  4. Navigate to label position via G90 absolute (no accumulated relative error).
  5. Draw label, then return to center via G90 absolute.

Usage:
    /usr/bin/python3 draw_size_test.py
"""

import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HUENIT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "huenit")
sys.path.insert(0, HUENIT_DIR)

import huenit_draw as hd
import huenit_write as hw

SIZES        = [100, 120, 140, 160, 180]
LABEL_SIZE   = 4.0   # mm letter height for the size label
LABEL_SPACE  = 0.8   # mm between letters
LABEL_MARGIN = 3.0   # mm inset from the square's corner


def touch_center(g):
    """Touch pen to paper at current position (marks center dot), then lift."""
    hd.pen_down(g)
    time.sleep(0.2)
    hd.pen_up(g)


def draw_labelled_square(g, size):
    """
    Assumes arm is at center with pen up.
    1. Draw square.
    2. Simple +s/2, +s/2 return to center (no label math involved).
    3. Touch center, re-stamp G92 at confirmed center position.
    4. Move to label via G90 absolute, draw label, return via G90 absolute.
    """
    s = float(size)
    label = str(size)
    label_width = hw.calculate_text_width(label, LABEL_SIZE, LABEL_SPACE)

    # Absolute label position relative to center (used with G90)
    lx = s / 2 - label_width - LABEL_MARGIN
    ly = -(s / 2) + LABEL_MARGIN

    # ── Square ────────────────────────────────────────────────────────────────
    hd.move_to(g, -s / 2, -s / 2)   # go to bottom-left corner (relative)
    hd.draw_square(g, s)             # draw square, ends at bottom-left, pen up

    # ── Simple reliable return to center ──────────────────────────────────────
    # From (-s/2, -s/2), move exactly (+s/2, +s/2) → back to (0, 0).
    # This is a single straight move with no label-width math — always correct.
    hd.move_to(g, s / 2, s / 2)

    # ── Touch center, re-stamp absolute origin ────────────────────────────────
    touch_center(g)
    g.send("G92 X0 Y0", wait_ok=True)   # confirmed center → new absolute origin
    time.sleep(0.05)

    # ── Label — just inside bottom-right corner ───────────────────────────────
    # Go to label start using G90 absolute (immune to any relative drift).
    g.send("G90", wait_ok=True)
    g.send(f"G1 X{lx:.3f} Y{ly:.3f} F{hd.TRAVEL_FEED}", wait_ok=True)
    g.wait_motion()
    g.send("G91", wait_ok=True)

    pen = hw.Pen(g, hd.Z_UP, hw.DEFAULT_DRAW_FEED)
    pen.is_up = True
    hw.render_text(pen, label, LABEL_SIZE, LABEL_SPACE)

    # ── Return to center via absolute positioning ─────────────────────────────
    g.send("G90", wait_ok=True)
    g.send(f"G1 X0.000 Y0.000 F{hd.TRAVEL_FEED}", wait_ok=True)
    g.wait_motion()
    g.send("G91", wait_ok=True)

    print(f"  ✅ {size}mm done")


def main():
    hd.check_ready()
    hd.load_calibration()
    hw.Z_UP       = hd.Z_UP
    hw.TILT_SLOPE = hd.TILT_SLOPE

    print("📐 Robot Ross — Drawing Area Size Test")
    print(f"   Squares: {SIZES} mm")
    print(f"   Port: {hd.PORT}")
    print()
    print("⚠️  Position the pen at the CENTER of the paper, then press Enter.")
    input("   Press Enter when ready...")
    print()

    g = hd.GCodeIO(hd.PORT, hd.BAUD)
    time.sleep(2.0)

    g.send("G21", wait_ok=True)    # mm units
    g.send("G91", wait_ok=True)    # relative moves
    time.sleep(0.1)

    # Mark origin dot and stamp absolute reference at confirmed center.
    print("Marking center...")
    touch_center(g)
    g.send("G92 X0 Y0", wait_ok=True)
    time.sleep(0.05)

    for size in SIZES:
        print(f"\n📐 Drawing {size}mm square...")
        draw_labelled_square(g, size)

    print("\n✅ All done! Pen is up — safe to remove paper.")
    g.close()


if __name__ == "__main__":
    main()
