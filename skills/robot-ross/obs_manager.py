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
OBS_PASSWORD = os.environ.get("OBS_PASSWORD", "Ross2026")

# ── Scenes (must match OBS scene names exactly) ────────────────────────────────
SCENE_WORKSPACE = "Workspace"   # full-screen camera, used as intro/outro
SCENE_ARTIST    = "Artist"      # camera + status text overlay, used during drawing

# ── Sources ────────────────────────────────────────────────────────────────────
SOURCE_CAM    = "Robot_Main_Cam"
SOURCE_STATUS = "Robot_Status"   # Text FreeType 2 source for live status overlay


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


def set_status(text):
    """Update the Robot_Status text overlay in OBS."""
    cl = get_client()
    try:
        cl.set_input_settings(
            name=SOURCE_STATUS,
            settings={"text": text},
            overlay=True,
        )
        print(f"Status set: {text!r}")
    except Exception as e:
        print(f"WARNING: could not update status text: {e}")


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


def start_show(buyer_name=None, prompt=None, record_only=False):
    """
    Full show sequence:
      1. Switch to Workspace (intro view — full camera)
      2. Start recording (always) + streaming (unless record_only=True)
      3. Switch to Artist (drawing view — camera + status overlay)
      4. Set status text to greet the buyer / show what's being drawn
    """
    cl = get_client()

    switch_scene(SCENE_WORKSPACE)

    if not record_only:
        stream = cl.get_stream_status()
        if not stream.output_active:
            cl.start_stream()
            print("Streaming started.")
    else:
        print("Record-only mode — skipping stream.")

    record = cl.get_record_status()
    if not record.output_active:
        cl.start_record()
        print("Recording started.")

    switch_scene(SCENE_ARTIST)

    status_text = "Robot Ross is drawing..."
    if buyer_name and prompt:
        status_text = f"Drawing for {buyer_name}: {prompt}"
    elif buyer_name:
        status_text = f"Drawing for {buyer_name}"
    elif prompt:
        status_text = f"Drawing: {prompt}"
    set_status(status_text)

    print("Show started — arm cam live.")


def stop_show():
    """
    End of show:
      1. Clear status text
      2. Switch back to Workspace
      3. Stop recording + streaming
    Returns path to the saved recording.
    """
    set_status("Thank you for watching Robot Ross!")

    switch_scene(SCENE_WORKSPACE)

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
    p_show = sub.add_parser("start_show", help="Intro → stream+record → drawing cam")
    p_show.add_argument("--record-only", action="store_true", help="Skip YouTube stream, record locally only")
    sub.add_parser("stop_show",     help="Outro → stop record+stream")

    p_scene = sub.add_parser("scene", help="Switch to a named scene")
    p_scene.add_argument("name", help=f"e.g. {SCENE_WORKSPACE!r} or {SCENE_ARTIST!r}")

    p_status = sub.add_parser("set-status", help=f"Update {SOURCE_STATUS!r} text overlay")
    p_status.add_argument("text")

    args = parser.parse_args()

    if args.cmd == "start_stream":   start_stream()
    elif args.cmd == "stop_stream":  stop_stream()
    elif args.cmd == "start_record": start_record()
    elif args.cmd == "stop_record":  stop_record()
    elif args.cmd == "status":       get_status()
    elif args.cmd == "start_show":   start_show(record_only=getattr(args, "record_only", False))
    elif args.cmd == "stop_show":    stop_show()
    elif args.cmd == "scene":        switch_scene(args.name)
    elif args.cmd == "set-status":   set_status(args.text)
    else:
        parser.print_help()
