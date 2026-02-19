#!/usr/bin/env python3
"""
huenit_sketch.py
----------------
Fetch an SVG from the internet and draw it on the Huenit arm.
Sends raw SVG path data (no potrace/vpype processing).

Usage:
    python3 huenit_sketch.py https://example.com/drawing.svg
    python3 huenit_sketch.py https://example.com/drawing.svg --size 80
    python3 huenit_sketch.py https://example.com/drawing.svg --out /tmp/fetched.svg
"""

import sys
import os
import argparse
import time
import urllib.request
import urllib.parse
import urllib.error
import tempfile
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MAX_SVG_BYTES  = 5 * 1024 * 1024   # 5 MB limit
FETCH_RETRIES  = 3
FETCH_TIMEOUT  = 15                 # seconds per attempt
RETRY_DELAY    = 2                  # seconds between retries

# Only these schemes allowed
ALLOWED_SCHEMES = {"http", "https"}


def sanitize_url(url):
    """
    Validate the URL is safe to fetch:
    - Must be http or https
    - No localhost / private IP targets
    Returns the sanitized URL string or raises ValueError.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme '{parsed.scheme}' not allowed — use http or https")

    host = parsed.hostname or ""
    # Block private/loopback addresses
    blocked = ("localhost", "127.", "10.", "192.168.", "172.16.", "172.17.",
               "172.18.", "172.19.", "172.2", "172.3", "::1", "0.0.0.0")
    if any(host == b or host.startswith(b) for b in blocked):
        raise ValueError(f"Host '{host}' is a private/loopback address — blocked for safety")

    return url


def fetch_svg(url, retries=FETCH_RETRIES, timeout=FETCH_TIMEOUT):
    """
    Download SVG from URL with retries.
    Returns SVG bytes on success, raises on failure.
    """
    headers = {"User-Agent": "RobotRoss/2.0 (Huenit arm plotter)"}
    req = urllib.request.Request(url, headers=headers)

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            print(f"  Fetching (attempt {attempt}/{retries}): {url}")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                content_len  = resp.headers.get("Content-Length", "?")
                print(f"  Content-Type: {content_type}  Length: {content_len}")

                data = resp.read(MAX_SVG_BYTES + 1)
                if len(data) > MAX_SVG_BYTES:
                    raise ValueError(f"SVG exceeds {MAX_SVG_BYTES//1024}KB limit")

                return data

        except (urllib.error.URLError, OSError) as e:
            last_err = e
            print(f"  Attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(RETRY_DELAY)

    raise RuntimeError(f"Failed to fetch SVG after {retries} attempts: {last_err}")


def validate_svg(data):
    """
    Basic validation that the bytes look like SVG (not HTML error page, etc.).
    Returns True or raises ValueError.
    """
    # Check for SVG signature in first 2KB
    head = data[:2048].lower()
    if b"<svg" not in head and b"<?xml" not in head:
        raise ValueError("Response does not appear to be an SVG file")
    return True


def draw_svg(svg_path, size=None, feed=None):
    """
    Call huenit_svg.py to draw the SVG on the arm.
    """
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, "huenit_svg.py"), svg_path]
    if size:
        cmd += ["--size", str(size)]
    if feed:
        cmd += ["--feed", str(feed)]

    print(f"  Drawing: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Fetch and draw an SVG from the internet")
    parser.add_argument("url",           help="HTTPS URL of the SVG file")
    parser.add_argument("--size",        type=float, default=None,
                        help="Max dimension in mm (default: huenit_svg.py default of 80)")
    parser.add_argument("--feed",        type=int,   default=None,
                        help="Drawing feed rate mm/min")
    parser.add_argument("--out",         default=None,
                        help="Save fetched SVG to this path (default: temp file)")
    parser.add_argument("--fetch-only",  action="store_true",
                        help="Download and validate only — do not draw")
    args = parser.parse_args()

    # 1. Sanitize URL
    try:
        url = sanitize_url(args.url)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # 2. Fetch SVG
    try:
        svg_data = fetch_svg(url)
    except (RuntimeError, ValueError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # 3. Validate
    try:
        validate_svg(svg_data)
        print(f"  SVG validated ({len(svg_data)} bytes)")
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # 4. Save to file
    if args.out:
        svg_path = args.out
        os.makedirs(os.path.dirname(os.path.abspath(svg_path)), exist_ok=True)
        with open(svg_path, "wb") as f:
            f.write(svg_data)
        print(f"  Saved to: {svg_path}")
    else:
        fd, svg_path = tempfile.mkstemp(suffix=".svg", prefix="robot_ross_fetch_")
        os.close(fd)
        with open(svg_path, "wb") as f:
            f.write(svg_data)
        print(f"  Saved to: {svg_path}")

    if args.fetch_only:
        print("  --fetch-only: skipping draw.")
        sys.exit(0)

    # 5. Draw
    success = draw_svg(svg_path, size=args.size, feed=args.feed)
    if not success:
        print("ERROR: huenit_svg.py returned an error")
        sys.exit(1)

    print("  Done.")


if __name__ == "__main__":
    main()
