#!/usr/bin/env python3
"""
ai_sketch.py
------------
Generate a pen-plotter-friendly SVG from a text prompt.
Defaults to a local Mistral model via Ollama; Claude Haiku (cloud) and
Apertus (Ollama) are available as alternates via --brain.

Usage:
    python3 ai_sketch.py "a happy little bird" --out /tmp/ai_sketch.svg
    python3 ai_sketch.py "a globe" --out /tmp/ai_sketch.svg --png-out /tmp/preview.png
    python3 ai_sketch.py "a globe" --brain haiku --out /tmp/ai_sketch.svg

Interface is drop-in compatible with quickdraw_compose.py.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

# Windows consoles default to cp1252 which can't encode emoji
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CREDENTIALS_FILE = os.path.expanduser("~/.openclaw/credentials/anthropic.json")

OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODELS = {
    "mistral": "ministral-3:8b",
    "apertus": "MichelRosselli/apertus:8b-instruct-2509-q4_k_m",
}

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
    # 1. Standard env var (works everywhere, no file needed)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # 2. OpenClaw credentials file (Mac / cloud setup)
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            data = json.load(f)
        profile = data.get("anthropic:default") or next(iter(data.values()))
        key = profile.get("apiKey") or profile.get("key")
        if key:
            return key
    raise FileNotFoundError(
        "Anthropic API key not found. Set the ANTHROPIC_API_KEY environment variable:\n"
        "  set ANTHROPIC_API_KEY=sk-ant-..."
    )


def _extract_svg(text: str) -> str:
    """Strip markdown fences / surrounding chatter and return the raw <svg>...</svg> block."""
    svg = text.strip()
    # Strip markdown fences (model often wraps in ```svg or ```xml despite instructions)
    svg = re.sub(r"^```[a-zA-Z]*\n?", "", svg)
    svg = re.sub(r"\n?```$", "", svg).strip()
    # Extract just the <svg>...</svg> block in case there's surrounding text
    match = re.search(r"(<svg[\s\S]*?</svg>)", svg, re.IGNORECASE)
    if match:
        svg = match.group(1)
    if not svg.startswith("<svg"):
        raise ValueError(f"Response does not look like SVG:\n{svg[:200]}")
    return _ensure_stroke_style(svg)


def _ensure_stroke_style(svg: str) -> str:
    """
    Wrap the SVG body in a stroke-only <g>, in case the model forgot the
    fill="none" stroke="black" pen-plotter styling. Harmless if already
    present — per-element attributes override the group default.
    """
    match = re.match(r"(<svg[^>]*>)([\s\S]*)(</svg>)\s*$", svg, re.IGNORECASE)
    if not match:
        return svg
    open_tag, body, close_tag = match.groups()
    return f'{open_tag}\n  <g fill="none" stroke="black" stroke-width="1.5">\n{body}\n  </g>\n{close_tag}'


def generate_svg_ollama(prompt: str, brain: str = "mistral") -> tuple:
    """Returns (svg_str, usage_dict) using a local Ollama model (Mistral by default)."""
    payload = json.dumps({
        "model": OLLAMA_MODELS[brain],
        "system": SYSTEM_PROMPT,
        "prompt": f"Draw: {prompt}",
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    svg = _extract_svg(result.get("response", ""))
    usage = {
        "input_tokens": result.get("prompt_eval_count", 0),
        "output_tokens": result.get("eval_count", 0),
    }
    return svg, usage


def generate_svg_haiku(prompt: str) -> tuple:
    """Returns (svg_str, usage_dict) using Claude Haiku (cloud)."""
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

    usage = result.get("usage", {})
    svg = _extract_svg(result["content"][0]["text"].strip())
    return svg, usage


def generate_svg(prompt: str, brain: str = "mistral") -> tuple:
    """Returns (svg_str, usage_dict). brain: mistral|apertus (local Ollama) or haiku (cloud)."""
    if brain == "haiku":
        return generate_svg_haiku(prompt)
    return generate_svg_ollama(prompt, brain)


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
        description="Generate a pen-plotter SVG from a text prompt"
    )
    parser.add_argument("prompt", help="Text description of what to draw")
    parser.add_argument("--out", default="/tmp/ai_sketch.svg", help="Output SVG path")
    parser.add_argument("--png-out", default=None, help="Optional PNG preview output path")
    parser.add_argument("--brain", default="mistral", choices=["mistral", "apertus", "haiku"],
                         help="Model to generate the SVG with")
    args = parser.parse_args()

    print(f"  Generating AI sketch for: {args.prompt!r} (brain={args.brain})")
    try:
        svg, usage = generate_svg(args.prompt, brain=args.brain)
    except Exception as e:
        print(f"  ❌ AI sketch generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w") as f:
        f.write(svg)

    elements = len(re.findall(r"<(path|circle|ellipse|line|polyline|rect)\b", svg))
    in_tok  = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    total   = in_tok + out_tok
    print(f"  ✅ SVG generated: {elements} elements → {args.out}")
    print(f"  TOKENS — input={in_tok} output={out_tok} total={total}")

    if args.png_out:
        ok = svg_to_png(args.out, args.png_out)
        if ok:
            print(f"  ✅ PNG preview: {args.png_out}")
        else:
            print("  ⚠  PNG preview failed", file=sys.stderr)


if __name__ == "__main__":
    main()
