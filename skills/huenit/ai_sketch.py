#!/usr/bin/env python3
"""
ai_sketch.py
------------
Generate a pen-plotter-friendly SVG from a text prompt using Claude Haiku.

Usage:
    python3 ai_sketch.py "a happy little bird" --out /tmp/ai_sketch.svg
    python3 ai_sketch.py "a globe" --out /tmp/ai_sketch.svg --png-out /tmp/preview.png

Interface is drop-in compatible with quickdraw_compose.py.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

CREDENTIALS_FILE = os.path.expanduser("~/.openclaw/credentials/anthropic.json")

SYSTEM_PROMPT = """\
You are a pen plotter artist. Generate SVG drawings optimised for a physical pen plotter.

STRICT rules:
- viewBox="0 0 125 125"  (units represent mm on paper)
- stroke="black" fill="none" on ALL elements — no fills, no gradients, no patterns
- Use ONLY: <path>, <circle>, <ellipse>, <line>, <polyline>, <rect>
- No <text>, <image>, <defs>, <clipPath>, or nested <svg>
- No transforms or complex group nesting
- 10–40 drawing elements maximum — the arm is slow, fewer = better quality
- Centre the composition in the canvas with a small margin (leave ~5mm border)
- Draw clean, recognisable outlines that work as single-line illustrations
- Output ONLY the raw <svg>...</svg> element — no markdown, no explanation, no code fences\
"""


def _load_api_key() -> str:
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"Anthropic credentials not found: {CREDENTIALS_FILE}")
    with open(CREDENTIALS_FILE) as f:
        data = json.load(f)
    profile = data.get("anthropic:default") or next(iter(data.values()))
    key = profile.get("apiKey") or profile.get("key")
    if not key:
        raise ValueError("No API key found in credentials file")
    return key


def generate_svg(prompt: str) -> str:
    api_key = _load_api_key()
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": f"Draw: {prompt}"}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.load(resp)

    svg = result["content"][0]["text"].strip()
    # Strip markdown fences (model often wraps in ```svg or ```xml despite instructions)
    svg = re.sub(r"^```[a-zA-Z]*\n?", "", svg)
    svg = re.sub(r"\n?```$", "", svg).strip()
    # Extract just the <svg>...</svg> block in case there's surrounding text
    match = re.search(r"(<svg[\s\S]*?</svg>)", svg, re.IGNORECASE)
    if match:
        svg = match.group(1)
    if not svg.startswith("<svg"):
        raise ValueError(f"Response does not look like SVG:\n{svg[:200]}")
    return svg


def svg_to_png(svg_path: str, png_path: str) -> bool:
    """Render SVG to PNG using qlmanage (macOS built-in)."""
    try:
        out_dir = os.path.dirname(os.path.abspath(png_path))
        subprocess.run(
            ["qlmanage", "-t", "-s", "1200", "-o", out_dir, svg_path],
            capture_output=True, timeout=30,
        )
        ql_out = svg_path + ".png"
        if os.path.exists(ql_out):
            os.rename(ql_out, png_path)
            return True
        return False
    except Exception as e:
        print(f"  ⚠  svg_to_png failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate a pen-plotter SVG from a text prompt using Claude Haiku"
    )
    parser.add_argument("prompt", help="Text description of what to draw")
    parser.add_argument("--out", default="/tmp/ai_sketch.svg", help="Output SVG path")
    parser.add_argument("--png-out", default=None, help="Optional PNG preview output path")
    args = parser.parse_args()

    print(f"  Generating AI sketch for: {args.prompt!r}")
    try:
        svg = generate_svg(args.prompt)
    except Exception as e:
        print(f"  ❌ AI sketch generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w") as f:
        f.write(svg)

    elements = len(re.findall(r"<(path|circle|ellipse|line|polyline|rect)\b", svg))
    print(f"  ✅ SVG generated: {elements} elements → {args.out}")

    if args.png_out:
        ok = svg_to_png(args.out, args.png_out)
        if ok:
            print(f"  ✅ PNG preview: {args.png_out}")
        else:
            print("  ⚠  PNG preview failed", file=sys.stderr)


if __name__ == "__main__":
    main()
