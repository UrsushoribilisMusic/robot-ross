#!/usr/bin/env python3
"""
artist_poller.py
----------------
Polls the Salesman API every POLL_INTERVAL seconds for new Shopify orders,
claims them atomically, runs bob_ross.py, then reports completion or failure.

Throttling: Waits for the robot arm to be free (JOB_LOCK) before claiming.
Retry: Implements exponential backoff for failed orders to avoid rapid failure loops.

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

# ── State ─────────────────────────────────────────────────────────────────────
_running = True
_failed_orders = {}  # {order_id: (count, next_retry_ts)}

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
    """
    fields = _extract_fields(order)
    otype   = fields["type"].lower()
    content = fields["content"]
    buyer   = fields["buyer"]

    base = [PYTHON, BOB_ROSS]
    buyer_args = ["--buyer", buyer] if buyer else []
    
    def _is_svg_source(value: str) -> bool:
        v = (value or "").strip()
        if not v: return False
        if os.path.isfile(v) and v.lower().endswith(".svg"): return True
        parsed = urlparse(v)
        if parsed.scheme in ("http", "https") and parsed.path.lower().endswith(".svg"): return True
        return v.lower().endswith(".svg")

    if otype == "write":
        return base + ["write", content] + buyer_args
    elif otype == "sketch":
        return base + ["sketch", content, "--direct"] + buyer_args
    elif otype == "fetch":
        return base + ["fetch", content] + buyer_args
    elif otype == "svg":
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
    """
    # 1. Throttling: Wait if the arm is already busy (e.g. human still pinning art)
    while os.path.exists(JOB_LOCK):
        if not _running: return False
        logger.info("POLLER robot busy (lock exists) — waiting 30s before checking queue...")
        time.sleep(30)

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
        return False

    order_id = order.get("id", "unknown")
    
    # 2b. Retry Backoff logic
    now_ts = time.time()
    if order_id in _failed_orders:
        count, next_retry = _failed_orders[order_id]
        if now_ts < next_retry:
            logger.info("POLLER order %s is in backoff (failed %d times). Skipping.", order_id, count)
            return False

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

    # 4. Ack
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
        rc = -1

    # 7. Report result
    if rc == 0:
        # Success: Clear failure tracking
        if order_id in _failed_orders: del _failed_orders[order_id]
        
        video_url = _get_video_url()
        logger.info("POLLER %s complete (video_url=%s)", order_id, video_url or "<none>")
        try:
            sc.complete(order_id, video_url=video_url, notes="")
        except Exception as e:
            logger.warning("POLLER complete call failed for %s: %s", order_id, e)
    else:
        # Failure: Track and apply backoff
        count, _ = _failed_orders.get(order_id, (0, 0))
        count += 1
        # Exponential backoff: 2, 4, 8, 16... capped at 60 minutes
        backoff_min = min(2 ** count, 60)
        backoff_sec = backoff_min * 60 
        _failed_orders[order_id] = (count, now_ts + backoff_sec)
        
        reason = f"bob_ross exited {rc}"
        logger.warning("POLLER %s failed (attempt %d): %s. Backoff until %s", 
                       order_id, count, reason, time.ctime(now_ts + backoff_sec))
        try:
            sc.fail(order_id, reason=reason, retryable=True)
        except Exception as e:
            logger.warning("POLLER fail call error for %s: %s", order_id, e)

    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    logger.info("POLLER starting — Artist Order Poller v2 (Throttled & Retry)")

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
                if not _running: break
                time.sleep(1)
    finally:
        caffeinate.terminate()
        logger.info("POLLER stopped")


if __name__ == "__main__":
    main()
