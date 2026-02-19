#!/usr/bin/env python3
"""
obs_manager.py
--------------
OBS Studio controller for Robot Ross live streaming.
Uses OBS WebSocket protocol v5 (OBS 28+).

Prerequisites:
  1. OBS Studio installed (https://obsproject.com)
  2. OBS → Tools → WebSocket Server Settings → Enable, set port + password
  3. pip3 install obsws-python

Usage:
    python3 obs_manager.py start_stream
    python3 obs_manager.py stop_stream
    python3 obs_manager.py start_record
    python3 obs_manager.py stop_record
    python3 obs_manager.py scene Scene_Drawing
    python3 obs_manager.py status

Environment variables (or edit defaults below):
    OBS_HOST      default: localhost
    OBS_PORT      default: 4455
    OBS_PASSWORD  default: (empty)
"""

import sys
import os
import json
import argparse

OBS_HOST     = os.environ.get("OBS_HOST", "localhost")
OBS_PORT     = int(os.environ.get("OBS_PORT", 4455))
OBS_PASSWORD = os.environ.get("OBS_PASSWORD", "")

# ── Scenes ─────────────────────────────────────────────────────────────────────
SCENE_INTRO   = "Scene_Intro"
SCENE_DRAWING = "Scene_Drawing"
SCENE_OUTRO   = "Scene_Outro"


def get_client():
    try:
        import obsws_python as obs
        cl = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD, timeout=5)
        return cl
    except ImportError:
        print("ERROR: obsws-python not installed. Run: pip3 install obsws-python")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to OBS at {OBS_HOST}:{OBS_PORT}")
        print(f"  → Make sure OBS is running and WebSocket server is enabled")
        print(f"  → Tools → WebSocket Server Settings → Enable")
        print(f"  → Error: {e}")
        sys.exit(1)


def start_stream():
    cl = get_client()
    status = cl.get_stream_status()
    if status.output_active:
        print("Stream already live.")
        return
    cl.start_stream()
    print("Streaming started.")


def stop_stream():
    cl = get_client()
    status = cl.get_stream_status()
    if not status.output_active:
        print("Stream not active.")
        return
    cl.stop_stream()
    print("Streaming stopped.")


def start_record():
    cl = get_client()
    status = cl.get_record_status()
    if status.output_active:
        print("Recording already active.")
        return
    cl.start_record()
    print("Recording started.")


def stop_record():
    cl = get_client()
    status = cl.get_record_status()
    if not status.output_active:
        print("Recording not active.")
        return
    resp = cl.stop_record()
    out = getattr(resp, "output_path", "unknown path")
    print(f"Recording saved: {out}")
    return out


def switch_scene(scene_name):
    cl = get_client()
    try:
        cl.set_current_program_scene(scene_name)
        print(f"Scene switched to: {scene_name}")
    except Exception as e:
        print(f"ERROR switching scene to '{scene_name}': {e}")
        print("  → Check that the scene name matches exactly in OBS")
        sys.exit(1)


def get_status():
    cl = get_client()
    stream  = cl.get_stream_status()
    record  = cl.get_record_status()
    scene   = cl.get_current_program_scene()
    version = cl.get_version()
    print(f"OBS version   : {version.obs_version}")
    print(f"Scene         : {scene.current_program_scene_name}")
    print(f"Streaming     : {'LIVE' if stream.output_active else 'off'}")
    print(f"Recording     : {'ACTIVE' if record.output_active else 'off'}")


def start_show(buyer_name=None):
    """
    Full show sequence:
      1. Switch to intro scene
      2. Start streaming + recording
      3. Switch to drawing scene
    Returns the scene names used (for logging).
    """
    cl = get_client()

    switch_scene(SCENE_INTRO)

    stream = cl.get_stream_status()
    if not stream.output_active:
        cl.start_stream()
        print("Streaming started.")

    record = cl.get_record_status()
    if not record.output_active:
        cl.start_record()
        print("Recording started.")

    switch_scene(SCENE_DRAWING)
    print("Show started — arm cam live.")


def stop_show():
    """
    End of show:
      1. Switch to outro scene (brief)
      2. Stop recording
      3. Stop streaming
    Returns path to the saved recording.
    """
    switch_scene(SCENE_OUTRO)

    cl = get_client()

    out_path = None
    record = cl.get_record_status()
    if record.output_active:
        resp = cl.stop_record()
        out_path = getattr(resp, "output_path", None)
        print(f"Recording saved: {out_path}")

    stream = cl.get_stream_status()
    if stream.output_active:
        cl.stop_stream()
        print("Stream ended.")

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OBS controller for Robot Ross")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("start_stream",  help="Start YouTube live stream")
    sub.add_parser("stop_stream",   help="Stop YouTube live stream")
    sub.add_parser("start_record",  help="Start local recording")
    sub.add_parser("stop_record",   help="Stop local recording")
    sub.add_parser("status",        help="Show OBS status")
    sub.add_parser("start_show",    help="Intro → stream+record → drawing cam")
    sub.add_parser("stop_show",     help="Outro → stop record+stream")

    p_scene = sub.add_parser("scene", help="Switch to a named scene")
    p_scene.add_argument("name", help=f"Scene name (e.g. {SCENE_INTRO}, {SCENE_DRAWING})")

    args = parser.parse_args()

    if args.cmd == "start_stream":   start_stream()
    elif args.cmd == "stop_stream":  stop_stream()
    elif args.cmd == "start_record": start_record()
    elif args.cmd == "stop_record":  stop_record()
    elif args.cmd == "status":       get_status()
    elif args.cmd == "start_show":   start_show()
    elif args.cmd == "stop_show":    stop_show()
    elif args.cmd == "scene":        switch_scene(args.name)
    else:
        parser.print_help()
