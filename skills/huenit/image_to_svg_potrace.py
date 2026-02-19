#!/usr/bin/env python3
"""
image_to_svg_potrace.py
-----------------------
Convert a photo to a pen-plotter SVG using potrace + vpype linesort.

Pipeline:
  1. Pillow  — grayscale, resize, edge detect, threshold → B&W bitmap (.pbm)
  2. potrace — traces bitmap → clean Bezier SVG (far fewer paths than vtracer)
  3. vpype linesort — reorders paths to minimise pen-up travel (reduces arm jumps)

Requires:
  potrace (brew install potrace)
  vpype   (pip3 install vpype — uses /Library/Developer/CommandLineTools/usr/bin/python3)

Usage:
    python3 image_to_svg_potrace.py photo.jpg
    python3 image_to_svg_potrace.py photo.jpg --out result.svg
    python3 image_to_svg_potrace.py photo.jpg --edges        # outline/edge mode (default)
    python3 image_to_svg_potrace.py photo.jpg --no-edges     # filled threshold mode
    python3 image_to_svg_potrace.py photo.jpg --turdsize 4 --opttolerance 0.5
    python3 image_to_svg_potrace.py photo.jpg --no-linesort  # skip vpype step
"""

import sys
import os
import argparse
import subprocess
import tempfile
import shutil

try:
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    print("  ❌ Pillow not installed. Run: pip3 install pillow")
    sys.exit(1)

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # HEIC unsupported, other formats still work

# ── Tool paths ────────────────────────────────────────────────────────────────
POTRACE_BIN   = shutil.which("potrace") or "/opt/homebrew/bin/potrace"
VPYPE_SCRIPT  = os.path.expanduser("~/Library/Python/3.9/bin/vpype")
VPYPE_PYTHON  = "/Library/Developer/CommandLineTools/usr/bin/python3"


def check_tools(linesort):
    ok = True
    if not os.path.exists(POTRACE_BIN):
        print(f"  ❌ potrace not found at {POTRACE_BIN}. Run: brew install potrace")
        ok = False
    if linesort and not os.path.exists(VPYPE_SCRIPT):
        print(f"  ❌ vpype not found at {VPYPE_SCRIPT}. Run: pip3 install vpype")
        ok = False
    return ok


def preprocess(image_path, max_px, threshold, contrast, blur, edges):
    """
    Prepare a B&W bitmap from the source image.
    Returns path to a temporary .pbm file.
    """
    img = Image.open(image_path).convert("L")
    w, h = img.size

    if max(w, h) > max_px:
        scale = max_px / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        print(f"  Resized: {w}x{h} → {img.size[0]}x{img.size[1]}px")
    else:
        print(f"  Size: {w}x{h}px")

    if edges:
        # Edge detection: find outlines, ignore fill/texture
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))
        img = img.filter(ImageFilter.FIND_EDGES)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        # Edges become black on white (potrace traces black regions)
        img = img.point(lambda p: 0 if p > threshold else 255, "L")
    else:
        img = ImageEnhance.Contrast(img).enhance(contrast)
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))
        img = img.point(lambda p: 0 if p > threshold else 255, "L")

    # potrace reads PBM (Portable Bitmap) format
    tmp = tempfile.NamedTemporaryFile(suffix=".pbm", delete=False)
    img.convert("1").save(tmp.name)
    tmp.close()
    return tmp.name


def run_potrace(pbm_path, svg_path, turdsize, alphamax, opttolerance):
    """
    Run potrace on a PBM file, output SVG.

    Key flags:
      --turdsize N     ignore speckles smaller than N pixels (default 2)
      --alphamax N     corner smoothness 0=sharp corners, 1=smooth (default 1.0)
      --opttolerance N Bezier optimisation tolerance (default 0.2, higher=fewer nodes)
    """
    cmd = [
        POTRACE_BIN,
        pbm_path,
        "--svg",
        "-o", svg_path,
        "--turdsize", str(turdsize),
        "--alphamax", str(alphamax),
        "--opttolerance", str(opttolerance),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace").strip()
        print(f"  ❌ potrace failed: {err[:300]}")
        return False
    return True


def sort_paths(svg_path):
    """
    Reorder <path> elements in SVG using a greedy nearest-neighbour algorithm
    to minimise total pen-up travel. Preserves original Bezier path data exactly.
    Overwrites svg_path in-place.
    """
    import xml.etree.ElementTree as ET
    import re
    import math

    ET.register_namespace("", "http://www.w3.org/2000/svg")

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except Exception as e:
        print(f"  ⚠  sort_paths: could not parse SVG: {e}")
        return False

    ns = "http://www.w3.org/2000/svg"

    def first_point(d):
        """Extract the first (x, y) coordinate from a path d attribute."""
        m = re.search(r'[Mm]\s*([-\d.]+)[,\s]+([-\d.]+)', d)
        if m:
            return float(m.group(1)), float(m.group(2))
        return 0.0, 0.0

    def last_point(d):
        """Approximate last point: find last coordinate pair before Z."""
        nums = re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)', d.split('Z')[0].split('z')[0])
        if len(nums) >= 2:
            return float(nums[-2]), float(nums[-1])
        return first_point(d)

    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    # Find the parent element that contains the paths
    def find_paths_with_parent(elem, parent=None):
        results = []
        for child in elem:
            tag = child.tag.split('}')[-1]
            if tag == 'path':
                results.append((elem, child))
            results.extend(find_paths_with_parent(child, elem))
        return results

    path_pairs = find_paths_with_parent(root)
    if len(path_pairs) < 2:
        return True  # nothing to sort

    # Group paths by parent
    from collections import defaultdict
    by_parent = defaultdict(list)
    for parent, path in path_pairs:
        by_parent[id(parent)].append((parent, path))

    for _, pairs in by_parent.items():
        if len(pairs) < 2:
            continue

        parent_elem = pairs[0][0]
        paths = [p for _, p in pairs]

        # Remove all paths from parent temporarily
        for p in paths:
            parent_elem.remove(p)

        # Greedy nearest-neighbour sort
        sorted_paths = []
        remaining = list(paths)
        cur = (0.0, 0.0)

        while remaining:
            best_i = min(range(len(remaining)),
                         key=lambda i: dist(cur, first_point(remaining[i].get('d', ''))))
            chosen = remaining.pop(best_i)
            sorted_paths.append(chosen)
            cur = last_point(chosen.get('d', ''))

        # Re-append in sorted order
        for p in sorted_paths:
            parent_elem.append(p)

    # Write back preserving XML declaration
    tree.write(svg_path, xml_declaration=True, encoding="unicode")
    print(f"  Paths reordered (nearest-neighbour, pen-up minimised)")
    return True


def count_svg_elements(svg_path):
    """Count drawable elements in SVG (path, polygon, polyline)."""
    try:
        with open(svg_path) as f:
            content = f.read()
        return (content.count("<path") +
                content.count("<polygon") +
                content.count("<polyline"))
    except Exception:
        return 0


def convert(image_path, out_path, max_px, threshold, contrast, blur, edges,
            turdsize, alphamax, opttolerance, linesort):

    print(f"  Input:   {image_path}")
    mode = "edge detection" if edges else "threshold"
    print(f"  Mode:    {mode}  threshold={threshold}  contrast={contrast}x  blur={blur}  max_px={max_px}")
    print(f"  potrace: turdsize={turdsize}  alphamax={alphamax}  opttolerance={opttolerance}")

    # Step 1: preprocess → .pbm
    pbm = preprocess(image_path, max_px, threshold, contrast, blur, edges)

    # Step 2: potrace → .svg
    print("  Running potrace…")
    ok = run_potrace(pbm, out_path, turdsize, alphamax, opttolerance)
    os.unlink(pbm)
    if not ok:
        return False

    n_paths = count_svg_elements(out_path)
    print(f"  potrace → {n_paths} elements")

    # Step 3: sort paths to minimise pen-up travel
    if linesort:
        print("  Sorting paths…")
        sort_paths(out_path)
        n_paths = count_svg_elements(out_path)

    est_min = max(1, n_paths // 30)
    print(f"  ✅ SVG saved: {out_path}  |  {n_paths} elements  |  est. ~{est_min} min to draw")
    return True


def main():
    parser = argparse.ArgumentParser(description="Convert image to SVG using potrace + vpype linesort")
    parser.add_argument("image", help="Input image (jpg, png, HEIC, etc.)")
    parser.add_argument("--out", default=None, help="Output SVG (default: same folder as input)")
    parser.add_argument("--max-px", type=int, default=800,
                        help="Resize to max N pixels on longest side (default 800)")
    parser.add_argument("--threshold", type=int, default=128,
                        help="B&W threshold 0-255 (default 128)")
    parser.add_argument("--contrast", type=float, default=2.0,
                        help="Contrast boost (default 2.0)")
    parser.add_argument("--blur", type=float, default=1.0,
                        help="Gaussian blur radius before threshold (default 1.0)")
    parser.add_argument("--edges", action="store_true", default=True,
                        help="Edge detection mode — outlines only (default ON)")
    parser.add_argument("--no-edges", dest="edges", action="store_false",
                        help="Disable edge detection, use filled threshold mode")
    parser.add_argument("--turdsize", type=int, default=4,
                        help="Suppress speckles smaller than N px (default 4)")
    parser.add_argument("--alphamax", type=float, default=0.8,
                        help="Corner smoothness 0-1.3 (default 0.8)")
    parser.add_argument("--opttolerance", type=float, default=0.3,
                        help="Bezier optimisation tolerance (default 0.3, higher=fewer nodes)")
    parser.add_argument("--no-linesort", dest="linesort", action="store_false", default=True,
                        help="Skip nearest-neighbour path sort step")
    parser.add_argument("--preview", action="store_true", help="Open result in Preview")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"  ❌ Image not found: {args.image}")
        sys.exit(1)

    if not check_tools(args.linesort):
        sys.exit(1)

    out_path = args.out or (os.path.splitext(args.image)[0] + "_potrace.svg")

    ok = convert(
        args.image, out_path,
        max_px=args.max_px,
        threshold=args.threshold,
        contrast=args.contrast,
        blur=args.blur,
        edges=args.edges,
        turdsize=args.turdsize,
        alphamax=args.alphamax,
        opttolerance=args.opttolerance,
        linesort=args.linesort,
    )

    if not ok:
        sys.exit(1)

    if args.preview:
        subprocess.run(["open", out_path])


if __name__ == "__main__":
    main()
