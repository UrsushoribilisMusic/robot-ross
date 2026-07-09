#!/usr/bin/env python3
"""
quickdraw_compose.py
--------------------
Parse a text prompt into objects, fetch a Quick Draw sketch for each,
and compose them into a single scene SVG.

Uses Ollama (Mistral by default, Apertus optional via --brain) to identify objects
and their approximate canvas positions. Falls back to evenly-spaced layout if
Ollama is unavailable.

Usage:
    python3 quickdraw_compose.py "a cat sitting on a bench" --out /tmp/scene.svg
    python3 quickdraw_compose.py "a house with a tree and a car" --seed 7
"""

import sys
import os
import json
import random
import argparse
import urllib.request

try:
    from PIL import Image, ImageDraw
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from quickdraw_to_svg import (
    QUICKDRAW_CATEGORIES,
    closest_category,
    fetch_samples,
)

OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODELS = {
    "mistral": "ministral-3:8b",
    "apertus": "MichelRosselli/apertus:8b-instruct-2509-q4_k_m",
}
CANVAS       = 500   # SVG viewBox size in px; Quick Draw native space is 255


def parse_scene_ollama(prompt, brain="mistral"):
    """
    Ask Ollama to identify drawable objects + rough positions.
    Returns a list of dicts: [{object, cx, cy, scale}, ...]
    cx/cy are 0-1 (fraction of canvas), scale is 0.2-0.8.
    """
    system = (
        "You are a scene parser for a drawing robot. "
        "Given a scene description, list the drawable objects with positions on a 0-1 canvas "
        "(0,0=top-left, 1,1=bottom-right). Max 5 objects. Spread them naturally.\n"
        "Use simple English object names (e.g. cat, dog, bench, person, tree, house).\n"
        "Return JSON with an 'objects' array. Each item: object, cx, cy, scale (0.2-0.8)."
    )

    payload = json.dumps({
        "model": OLLAMA_MODELS[brain],
        "prompt": f"Scene: {prompt}",
        "system": system,
        "stream": False,
        "format": "json",
    }).encode()

    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            parsed = json.loads(result["response"])
            # Response might be the array directly or {"objects": [...]}
            if isinstance(parsed, list):
                return parsed
            for key in ("objects", "items", "scene"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
    except Exception as e:
        print(f"  Ollama parse error: {e}")
    return None


def fallback_layout(objects):
    """Evenly space objects horizontally across the canvas."""
    n = len(objects)
    result = []
    for i, obj in enumerate(objects):
        cx = (i + 1) / (n + 1)
        result.append({"object": obj, "cx": cx, "cy": 0.55, "scale": 0.45})
    return result


def object_to_strokes(obj_name):
    """Find Quick Draw category and return a random stroke list."""
    cat = closest_category(obj_name)
    if not cat:
        print(f"  Skipping '{obj_name}' — no matching Quick Draw category")
        return None, None
    samples = fetch_samples(cat)
    if not samples:
        print(f"  Skipping '{cat}' — no samples available")
        return None, None
    return cat, random.choice(samples)


def compose_svg(scene_objects):
    """
    Compose Quick Draw strokes into a single SVG.

    scene_objects: list of {object, cx, cy, scale}
      cx/cy: 0-1 fractions of CANVAS
      scale: 0-1 fraction of CANVAS (object bounding box size)
    """
    all_paths = []
    stats = []

    for item in scene_objects:
        obj_name = item.get("object", "")
        cx = float(item.get("cx", 0.5)) * CANVAS
        cy = float(item.get("cy", 0.5)) * CANVAS
        # scale is fraction of canvas; Quick Draw strokes are 0-255
        obj_size = float(item.get("scale", 0.4)) * CANVAS
        stroke_scale = obj_size / 255.0

        cat, strokes = object_to_strokes(obj_name)
        if strokes is None:
            continue

        # Center strokes at (cx, cy)
        ox = cx - 127.5 * stroke_scale
        oy = cy - 127.5 * stroke_scale

        for stroke in strokes:
            xs, ys = stroke[0], stroke[1]
            if not xs:
                continue
            pts = [
                (ox + xs[i] * stroke_scale, oy + ys[i] * stroke_scale)
                for i in range(len(xs))
            ]
            d = f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"
            for px, py in pts[1:]:
                d += f" L {px:.2f},{py:.2f}"
            all_paths.append(f'  <path d="{d}" />')

        n_pts = sum(len(s[0]) for s in strokes)
        stats.append(f"'{cat}' ({len(strokes)} strokes, {n_pts} pts)")
        print(f"  Added {stats[-1]} at ({cx:.0f},{cy:.0f}) scale={stroke_scale:.3f}")

    if not all_paths:
        return None

    path_str = "\n".join(all_paths)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS} {CANVAS}">\n'
        f'  <g fill="none" stroke="black" stroke-width="4"'
        f' stroke-linecap="round" stroke-linejoin="round">\n'
        f"{path_str}\n"
        f"  </g>\n"
        f"</svg>\n"
    )
    return svg, stats


def render_png(scene_objects, png_path, img_size=900):
    """
    Render a Quick Draw scene directly to PNG using Pillow.
    Much more reliable than qlmanage for preview purposes.
    scene_objects: same list of {object, cx, cy, scale} used by compose_svg.
    """
    if not _PIL_AVAILABLE:
        print("  ⚠  Pillow not available — cannot render PNG preview")
        return False

    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)

    scale_factor = img_size / CANVAS   # CANVAS=500 → img_size px

    for item in scene_objects:
        obj_name = item.get("object", "")
        cx = float(item.get("cx", 0.5)) * CANVAS
        cy = float(item.get("cy", 0.5)) * CANVAS
        obj_size = float(item.get("scale", 0.4)) * CANVAS
        stroke_scale = obj_size / 255.0

        cat, strokes = object_to_strokes(obj_name)
        if strokes is None:
            continue

        ox = cx - 127.5 * stroke_scale
        oy = cy - 127.5 * stroke_scale

        for stroke in strokes:
            xs, ys = stroke[0], stroke[1]
            if len(xs) < 2:
                continue
            pts = [
                (
                    (ox + xs[i] * stroke_scale) * scale_factor,
                    (oy + ys[i] * stroke_scale) * scale_factor,
                )
                for i in range(len(xs))
            ]
            draw.line(pts, fill="black", width=4, joint="curve")

    # Add a subtle border
    draw.rectangle([2, 2, img_size - 3, img_size - 3], outline="#cccccc", width=1)

    img.save(png_path)
    print(f"  PNG preview: {png_path} ({img_size}x{img_size}px)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Compose a Quick Draw scene SVG from a text prompt")
    parser.add_argument("prompt", help="Scene description, e.g. 'a dog and a cat on a bench'")
    parser.add_argument("--out", default="/tmp/quickdraw_scene.svg", help="Output SVG path")
    parser.add_argument("--png-out", default=None, help="Also render a PNG preview to this path")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--no-llm", action="store_true", help="Skip Ollama, use simple word extraction")
    parser.add_argument("--brain", default="mistral", choices=["mistral", "apertus"], help="Ollama model for scene parsing")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    print(f"  Prompt: {args.prompt!r}")

    # ── Parse scene ───────────────────────────────────────────────────────────
    scene = None
    if not args.no_llm:
        print(f"  Parsing scene with Ollama ({args.brain})…")
        scene = parse_scene_ollama(args.prompt, brain=args.brain)

    if scene:
        print(f"  Objects from Ollama: {[o.get('object') for o in scene]}")
    else:
        # Fallback: pull nouns from the prompt by trying each word/bigram
        print("  Falling back to word-by-word extraction…")
        STOP_WORDS = {
            "a", "an", "the", "and", "or", "but", "with", "on", "in", "at",
            "to", "of", "for", "from", "by", "is", "are", "was", "were",
            "its", "their", "some", "two", "three", "four", "five", "sitting",
            "standing", "walking", "running", "next", "near", "beside",
            "under", "over", "behind", "front", "big", "small", "large",
        }
        words = args.prompt.lower().split()
        found = []
        i = 0
        while i < len(words):
            if words[i] in STOP_WORDS:
                i += 1
                continue
            # Try bigram first
            if i + 1 < len(words) and words[i + 1] not in STOP_WORDS:
                bigram = words[i] + " " + words[i + 1]
                cat = closest_category(bigram)
                if cat:
                    found.append(cat)
                    i += 2
                    continue
            cat = closest_category(words[i])
            if cat:
                found.append(cat)
            i += 1
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for c in found:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        if not unique:
            print("  ERROR: Could not identify any drawable objects in the prompt.")
            return 1
        scene = fallback_layout(unique)
        print(f"  Objects (word extraction): {[o['object'] for o in scene]}")

    # ── Compose SVG ───────────────────────────────────────────────────────────
    result = compose_svg(scene)
    if result is None:
        print("  ERROR: No strokes generated — could not compose scene.")
        return 1

    svg, stats = result
    with open(args.out, "w") as f:
        f.write(svg)

    total_paths = svg.count("<path")
    print(f"  Scene SVG: {args.out}  |  {total_paths} paths  |  {', '.join(stats)}")

    if args.png_out:
        render_png(scene, args.png_out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
