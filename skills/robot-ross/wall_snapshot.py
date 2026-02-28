#!/usr/bin/env python3
"""
wall_snapshot.py
----------------
Capture a screenshot of the Wall of Fame board camera (via OBS) and push
it to the Salesman VPS to be served at https://api.robotross.art/wall.

Usage:
    /usr/bin/python3 wall_snapshot.py

Trigger via Telegram: "wall snapshot"
Trigger via desktop: Wall Snapshot.command shortcut
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
LOG_FILE     = os.path.join(SCRIPT_DIR, "bob_ross.log")
WALL_CONFIG  = os.path.join(SCRIPT_DIR, "wall_config.json")
SALESMAN_CFG = os.path.join(SCRIPT_DIR, ".salesman_config")
OBS_SOURCE   = "macOS Screen Capture"
UPLOAD_URL   = "https://api.robotross.art/wall/snapshot"
LOCAL_OUT    = "/tmp/wall_snapshot.jpg"


def _load_token() -> str:
    """Read ARTIST_API_TOKEN from .salesman_config."""
    if os.path.exists(SALESMAN_CFG):
        with open(SALESMAN_CFG) as f:
            for line in f:
                if line.startswith("ARTIST_API_TOKEN="):
                    return line.strip().split("=", 1)[1]
    raise ValueError(f"ARTIST_API_TOKEN not found in {SALESMAN_CFG}")


def _load_crop():
    """Return [left, top, right, bottom] crop box or None if not configured."""
    if os.path.exists(WALL_CONFIG):
        with open(WALL_CONFIG) as f:
            cfg = json.load(f)
        return cfg.get("crop")
    return None


def log(event, detail=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {event}" + (f" — {detail}" if detail else "")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def capture_screenshot() -> bool:
    """Use OBS WebSocket to capture the board camera source as a JPEG."""
    try:
        import obsws_python as obs
        cl = obs.ReqClient(host="localhost", port=4455, password="Ross2026", timeout=5)
        resp = cl.get_source_screenshot(
            name=OBS_SOURCE,
            img_format="jpg",
            width=1920,
            height=1080,
            quality=85,
        )
        # Response contains base64-encoded image — decode and save
        import base64
        data_url = resp.image_data  # "data:image/jpg;base64,..."
        b64 = data_url.split(",", 1)[1]
        with open(LOCAL_OUT, "wb") as f:
            f.write(base64.b64decode(b64))
        log("SNAPSHOT", f"captured → {LOCAL_OUT}")
        return True
    except Exception as e:
        log("SNAPSHOT ERROR", f"OBS capture failed: {e}")
        return False


def crop_image(path: str, crop: list) -> bool:
    """Crop the image to [left, top, right, bottom] using Pillow."""
    try:
        from PIL import Image
        img = Image.open(path)
        img = img.crop(tuple(crop))
        img.save(path, "JPEG", quality=85)
        log("SNAPSHOT", f"cropped to {img.size[0]}×{img.size[1]}px (box={crop})")
        return True
    except Exception as e:
        log("SNAPSHOT ERROR", f"crop failed: {e}")
        return False


def push_to_vps() -> bool:
    """POST the snapshot to the Salesman HTTPS endpoint."""
    try:
        token = _load_token()
        with open(LOCAL_OUT, "rb") as f:
            data = f.read()
        req = urllib.request.Request(
            UPLOAD_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/jpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode(errors="replace")
            log("SNAPSHOT", f"uploaded → {UPLOAD_URL} ({resp.status}) {body[:80]}")
        return True
    except Exception as e:
        log("SNAPSHOT ERROR", f"upload failed: {e}")
        return False


def main():
    log("WALL SNAPSHOT", "starting")

    if not capture_screenshot():
        print("❌ Could not capture screenshot from OBS.")
        print("   Make sure OBS is running with the board camera source.")
        sys.exit(1)

    crop = _load_crop()
    if crop:
        crop_image(LOCAL_OUT, crop)
    else:
        log("SNAPSHOT", "no crop configured — uploading full frame (set crop in wall_config.json)")

    if not push_to_vps():
        print("❌ Could not upload snapshot to Salesman.")
        print(f"   Image saved locally at {LOCAL_OUT}")
        sys.exit(1)

    print("✅ Wall snapshot updated at https://api.robotross.art/wall")
    log("WALL SNAPSHOT", "done — https://api.robotross.art/wall")


if __name__ == "__main__":
    main()
