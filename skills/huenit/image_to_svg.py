#!/usr/bin/env python3
"""
image_to_svg.py
---------------
Convert a photo or image to a pen-plotter-ready SVG using vtracer.

Preprocesses the image (grayscale + contrast boost + threshold) before
tracing so the output has clean, minimal paths — no fills, no noise.

Usage:
    python3 image_to_svg.py photo.jpg
    python3 image_to_svg.py photo.jpg --out result.svg
    python3 image_to_svg.py photo.jpg --edges           # silhouette/outline mode
    python3 image_to_svg.py photo.jpg --edges --auto    # auto-tune to ~2000 segments
    python3 image_to_svg.py photo.jpg --preview         # open result in Preview

Output SVG is saved next to the input file unless --out is specified.
"""

import sys
import os
import argparse
import subprocess
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import tempfile

try:
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    print("  ❌ Pillow not installed. Run: pip3 install pillow")
    sys.exit(1)

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()  # adds HEIC/HEIF support to Pillow
except ImportError:
    pass  # HEIC not supported but other formats still work

try:
    import vtracer
except ImportError:
    print("  ❌ vtracer not installed. Run: pip3 install vtracer")
    sys.exit(1)

# Auto-tune target range (can be overridden via IMAGE_SVG_TARGET env var)
AUTO_TARGET     = int(os.environ.get("IMAGE_SVG_TARGET", 4000))
AUTO_TOLERANCE  = 0.20   # ±20% of target
AUTO_MAX_ITER   = 10


def count_segments(svg_path):
    """Count path segments (L, C, Q commands) in an SVG file."""
    try:
        with open(svg_path) as f:
            content = f.read()
        path_count = content.count("<path")
        seg_count = sum(
            content.count(f' {c}') + content.count(f',{c}') + content.count(f'"{c}')
            for c in ['L', 'C', 'Q']
        )
        return path_count, seg_count
    except Exception:
        return 0, 0


def preprocess(image_path, threshold, contrast, max_px, blur, edges):
    """Convert image to high-contrast B&W suitable for tracing. Returns temp file path."""
    img = Image.open(image_path).convert("L")  # grayscale

    # Resize to max_px on longest side — fewer pixels = fewer paths = faster draw
    w, h = img.size
    if max(w, h) > max_px:
        scale = max_px / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        print(f"  📐 Resized:    {w}x{h} → {img.size[0]}x{img.size[1]}px")
    else:
        print(f"  📐 Size:       {w}x{h}px (no resize needed)")

    if edges:
        # Edge detection mode — finds outlines/silhouette, ignores fill/texture
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))
        img = img.filter(ImageFilter.FIND_EDGES)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        # Invert: edges become black on white (pen plotter friendly)
        img = img.point(lambda p: 0 if p > threshold else 255, "L")
    else:
        # Standard threshold mode
        img = ImageEnhance.Contrast(img).enhance(contrast)
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))
        img = img.point(lambda p: 255 if p > threshold else 0, "L")

    # Save to temp file for vtracer
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    tmp.close()
    return tmp.name


def trace(tmp_path, out_path, speckle, corner, smoothness):
    """Run vtracer on preprocessed image."""
    vtracer.convert_image_to_svg_py(
        tmp_path,
        out_path,
        colormode="binary",
        hierarchical="flat",
        mode="spline",
        filter_speckle=speckle,
        corner_threshold=corner,
        length_threshold=smoothness,
        max_iterations=10,
        splice_threshold=45,
    )


def convert(image_path, out_path, threshold, contrast, max_px, blur,
            speckle, corner, smoothness, edges, auto):

    print(f"  📷 Input:      {image_path}")

    # Preprocess once — same for all iterations
    mode_label = "edge detection" if edges else "threshold"
    print(f"  🔍 Mode:       {mode_label}")
    print(f"  ⚙️  Threshold:  {threshold}  Contrast: {contrast}x  Blur: {blur}  MaxPx: {max_px}")
    tmp_path = preprocess(image_path, threshold, contrast, max_px, blur, edges)

    if auto:
        # Binary search on smoothness to hit AUTO_TARGET segments
        lo_smooth = 0.5
        hi_smooth = 50.0
        lo_speckle = max(1, speckle // 2)
        hi_speckle = speckle * 4
        best_path = out_path
        best_segs = None

        print(f"  🎯 Auto-tune: target ~{AUTO_TARGET} segments (±{int(AUTO_TOLERANCE*100)}%)")

        for i in range(AUTO_MAX_ITER):
            cur_smooth  = (lo_smooth + hi_smooth) / 2
            cur_speckle = int((lo_speckle + hi_speckle) / 2)

            trace(tmp_path, out_path, cur_speckle, corner, cur_smooth)
            paths, segs = count_segments(out_path)

            print(f"  [{i+1}/{AUTO_MAX_ITER}] smoothness={cur_smooth:.1f}  speckle={cur_speckle}"
                  f"  → {paths} paths, {segs} segments")

            if segs == 0:
                # No output — back off
                hi_smooth  = cur_smooth
                hi_speckle = cur_speckle
                continue

            best_segs = segs
            lo_target = AUTO_TARGET * (1 - AUTO_TOLERANCE)
            hi_target = AUTO_TARGET * (1 + AUTO_TOLERANCE)

            if lo_target <= segs <= hi_target:
                print(f"  ✅ Target reached!")
                break
            elif segs > hi_target:
                # Too many segments — increase smoothness/speckle
                lo_smooth  = cur_smooth
                lo_speckle = cur_speckle
            else:
                # Too few segments — decrease smoothness/speckle
                hi_smooth  = cur_smooth
                hi_speckle = cur_speckle

        paths, segs = count_segments(out_path)

    else:
        # Manual mode — single pass
        print(f"  ⚙️  Speckle:   {speckle}  Smoothness: {smoothness}")
        trace(tmp_path, out_path, speckle, corner, smoothness)
        paths, segs = count_segments(out_path)

    os.unlink(tmp_path)

    print(f"  ✅ SVG saved:  {out_path}")
    print(f"  📐 Paths:      {paths}  |  Segments: ~{segs}")
    print(f"  ⏱  Est. draw:  ~{segs // 500 + 1} min at normal speed")


def main():
    parser = argparse.ArgumentParser(description="Convert image to plotter-ready SVG")
    parser.add_argument("image", help="Input image (jpg, png, HEIC, etc.)")
    parser.add_argument("--out", type=str, default=None,
                        help="Output SVG path (default: same folder as input)")
    parser.add_argument("--threshold", type=int, default=128,
                        help="B&W threshold 0-255 (default 128 — lower = more black)")
    parser.add_argument("--contrast", type=float, default=2.0,
                        help="Contrast boost before threshold (default 2.0)")
    parser.add_argument("--max-px", type=int, default=800,
                        help="Resize image to max N pixels on longest side (default 800)")
    parser.add_argument("--blur", type=float, default=1.5,
                        help="Gaussian blur radius before threshold (default 1.5)")
    parser.add_argument("--speckle", type=int, default=8,
                        help="Starting speckle filter — ignore islands smaller than N px (default 8)")
    parser.add_argument("--corner", type=int, default=60,
                        help="Corner threshold in degrees (default 60)")
    parser.add_argument("--smoothness", type=float, default=6.0,
                        help="Path smoothness — higher = fewer nodes (default 6.0)")
    parser.add_argument("--edges", action="store_true",
                        help="Edge detection mode — draws outlines/silhouette only (great for portraits)")
    parser.add_argument("--auto", action="store_true",
                        help=f"Auto-tune smoothness/speckle to reach ~{AUTO_TARGET} segments")
    parser.add_argument("--preview", action="store_true",
                        help="Open the SVG in Preview when done")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"  ❌ Image not found: {args.image}")
        sys.exit(1)

    out_path = args.out or (os.path.splitext(args.image)[0] + "_traced.svg")

    convert(
        args.image,
        out_path,
        threshold=args.threshold,
        contrast=args.contrast,
        max_px=args.max_px,
        blur=args.blur,
        speckle=args.speckle,
        corner=args.corner,
        smoothness=args.smoothness,
        edges=args.edges,
        auto=args.auto,
    )

    if args.preview:
        subprocess.run(["open", out_path])


if __name__ == "__main__":
    main()
