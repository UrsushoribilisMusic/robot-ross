#!/usr/bin/env python3
"""
artist_poller.py
----------------
Polls the Salesman API every POLL_INTERVAL seconds for new Shopify orders,
claims them atomically, runs bob_ross.py, then reports completion or failure.

Usage:
    /usr/bin/python3 artist_poller.py
    POLL_INTERVAL=60 /usr/bin/python3 artist_poller.py   # override interval

Stop: Ctrl+C or SIGTERM.
"""

import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from urllib.parse import urlparse

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = "/usr/bin/python3"
BOB_ROSS = os.path.join(SCRIPT_DIR, "bob_ross.py")
JOB_LOCK = "/tmp/robot_ross_running.lock"
LOG_FILE = os.path.join(SCRIPT_DIR, "bob_ross.log")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger("artist_poller")

# ── Import Salesman client (same directory) ───────────────────────────────────
sys.path.insert(0, SCRIPT_DIR)
import salesman_client as sc
from salesman_client import SalesmanAPIError

# ── Graceful shutdown ─────────────────────────────────────────────────────────
_running = True


def _handle_stop(signum, frame):
    global _running
    logger.info("POLLER received stop signal — will exit after current cycle")
    _running = False


signal.signal(signal.SIGINT, _handle_stop)
signal.signal(signal.SIGTERM, _handle_stop)


# ── Config ────────────────────────────────────────────────────────────────────
def _poll_interval() -> int:
    cfg = sc._load_config()
    try:
        return int(cfg.get("POLL_INTERVAL", 180))
    except ValueError:
        return 180


# ── Video URL ─────────────────────────────────────────────────────────────────
def _get_video_url() -> str:
    """Read the last video URL written to orders.xlsx by bob_ross.py."""
    try:
        import order_log
        return order_log.get_last_video_url() or ""
    except Exception as e:
        logger.warning("Could not read video URL from order_log: %s", e)
        return ""


# ── Field extraction (backward-compatible) ────────────────────────────────────
def _extract_fields(order: dict) -> dict:
    """
    Extract normalised fields from an order with payload-first fallback.

    Priority (mirrors JS ?? operator):
      type    : payload.type    ?? order.type
      content : payload.content ?? order.content ?? payload.notes
      buyer   : payload.buyer   ?? order.buyer   ?? payload.customer
      notes   : payload.notes   ?? order.notes
    """
    p = order.get("payload") or {}
    return {
        "type":    p.get("type")    or order.get("type", ""),
        "content": p.get("content") or order.get("content") or p.get("notes", ""),
        "buyer":   p.get("buyer")   or order.get("buyer")   or p.get("customer", ""),
        "notes":   p.get("notes")   or order.get("notes", ""),
    }


# ── Command builder ───────────────────────────────────────────────────────────
def _build_command(order: dict):
    """
    Map order dict → bob_ross.py argv list.
    Returns None for unknown order types (caller should fail the order).
    """
    fields = _extract_fields(order)
    otype   = fields["type"].lower()
    content = fields["content"]
    buyer   = fields["buyer"]

    base = [PYTHON, BOB_ROSS]
    buyer_args = ["--buyer", buyer] if buyer else []
    
    def _is_svg_source(value: str) -> bool:
        v = (value or "").strip()
        if not v:
            return False
        if os.path.isfile(v) and v.lower().endswith(".svg"):
            return True
        parsed = urlparse(v)
        if parsed.scheme in ("http", "https") and parsed.path.lower().endswith(".svg"):
            return True
        return v.lower().endswith(".svg")

    if otype == "write":
        return base + ["write", content] + buyer_args
    elif otype == "sketch":
        return base + ["sketch", content, "--direct"] + buyer_args
    elif otype == "fetch":
        return base + ["fetch", content] + buyer_args
    elif otype == "svg":
        # Shopify "graphics/svg" orders often send a text prompt, not an SVG file/URL.
        # Route prompt-like values to sketch so drawing can still execute.
        if _is_svg_source(content):
            return base + ["svg", content] + buyer_args
        return base + ["sketch", content, "--direct"] + buyer_args
    elif otype == "draw":
        return base + ["draw", content] + buyer_args
    elif otype == "image":
        return base + ["image", content] + buyer_args
    else:
        return None


# ── Single poll cycle ─────────────────────────────────────────────────────────
def poll_once() -> bool:
    """
    Run one poll cycle.
    Returns True if an order was processed (successfully or not), False otherwise.
    """
    # 1. Skip if the arm is already busy
    if os.path.exists(JOB_LOCK):
        logger.info("POLLER robot busy (lock exists) — skipping poll")
        return False

    # 2. Fetch the next pending order
    try:
        order = sc.get_incoming()
    except SalesmanAPIError as e:
        logger.warning("POLLER GET incoming failed (HTTP %s) — skipping: %s", e.status_code, e)
        return False
    except Exception as e:
        logger.warning("POLLER network error on GET incoming — skipping: %s", e)
        return False

    if order is None:
        logger.info("POLLER no orders — sleeping")
        return False

    order_id = order.get("id", "unknown")
    fields = _extract_fields(order)
    logger.info(
        "POLLER order %s received: type=%s buyer=%s content=%r",
        order_id,
        fields["type"],
        fields["buyer"],
        fields["content"][:60],
    )

    # 3. Claim atomically
    idem_key = str(uuid.uuid4())
    try:
        sc.claim(order_id, idem_key)
        logger.info("POLLER claimed %s (idempotency_key=%s)", order_id, idem_key)
    except SalesmanAPIError as e:
        if e.status_code == 409:
            logger.info("POLLER %s already claimed by another poller — skipping", order_id)
        else:
            logger.warning("POLLER claim failed for %s: %s", order_id, e)
        return False
    except Exception as e:
        logger.warning("POLLER claim network error for %s — skipping: %s", order_id, e)
        return False

    # 4. Ack (non-fatal if it fails — order is already claimed)
    try:
        sc.ack(order_id)
        logger.info("POLLER acked %s", order_id)
    except Exception as e:
        logger.warning("POLLER ack failed for %s (continuing): %s", order_id, e)

    # 5. Build bob_ross.py command
    cmd = _build_command(order)
    if cmd is None:
        reason = f"unknown order type: {order.get('type')!r}"
        logger.warning("POLLER %s — %s", order_id, reason)
        try:
            sc.fail(order_id, reason=reason, retryable=False)
        except Exception as fe:
            logger.warning("POLLER fail call error for %s: %s", order_id, fe)
        return True

    logger.info("POLLER running: %s", " ".join(cmd))

    # 6. Run bob_ross.py as a subprocess
    try:
        result = subprocess.run(cmd, cwd=SCRIPT_DIR)
        rc = result.returncode
    except Exception as e:
        logger.error("POLLER subprocess launch failed for %s: %s", order_id, e)
        try:
            sc.fail(order_id, reason=f"subprocess launch failed: {e}", retryable=True)
        except Exception as fe:
            logger.warning("POLLER fail call error for %s: %s", order_id, fe)
        return True

    # 7. Report result
    if rc == 0:
        video_url = _get_video_url()
        logger.info(
            "POLLER %s complete (video_url=%s)", order_id, video_url or "<none>"
        )
        try:
            sc.complete(order_id, video_url=video_url, notes="")
        except Exception as e:
            logger.warning("POLLER complete call failed for %s: %s", order_id, e)
    else:
        reason = f"bob_ross exited {rc}"
        logger.warning("POLLER %s failed: %s", order_id, reason)
        try:
            sc.fail(order_id, reason=reason, retryable=True)
        except Exception as e:
            logger.warning("POLLER fail call error for %s: %s", order_id, e)

    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    logger.info("POLLER starting — Artist Order Poller v1")

    # Validate config before entering the loop
    try:
        sc._get_config()
    except ValueError as e:
        logger.error("POLLER config error: %s", e)
        sys.exit(1)

    interval = _poll_interval()
    logger.info("POLLER poll interval: %ds (%.1f min)", interval, interval / 60)

    # Prevent Mac from sleeping while polling
    caffeinate = subprocess.Popen(["caffeinate", "-d", "-i"])
    logger.info("POLLER caffeinate started (pid %d)", caffeinate.pid)

    try:
        while _running:
            poll_once()
            # Sleep in 1-second ticks so SIGINT/SIGTERM is handled promptly
            for _ in range(interval):
                if not _running:
                    break
                time.sleep(1)
    finally:
        caffeinate.terminate()
        logger.info("POLLER stopped")


if __name__ == "__main__":
    main()
