#!/usr/bin/env python3
"""
salesman_client.py
------------------
Thin HTTP client for the Salesman REST API.

Config is loaded in priority order:
  1. Environment variables: SALESMAN_URL, ARTIST_API_TOKEN
  2. .salesman_config file (KEY=VALUE lines, same directory as this script)

Usage:
    import salesman_client as sc
    order = sc.get_incoming()
    sc.claim(order["id"], idempotency_key)
    sc.ack(order["id"])
    sc.complete(order["id"], video_url="https://...", notes="")
    sc.fail(order["id"], reason="...", retryable=True)
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".salesman_config")


class SalesmanAPIError(Exception):
    """Raised on non-2xx HTTP responses from the Salesman API."""

    def __init__(self, status_code: int, body: str, request_id: str = ""):
        self.status_code = status_code
        self.body = body
        self.request_id = request_id
        super().__init__(
            f"HTTP {status_code}: {body[:200]} (X-Request-Id: {request_id})"
        )


def _load_config() -> dict:
    """Load config from .salesman_config file, then override with env vars."""
    cfg = {}
    if os.path.exists(_CONFIG_FILE):
        with open(_CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    cfg[k.strip()] = v.strip()

    # Env vars take priority over file
    for key in ("SALESMAN_URL", "ARTIST_API_TOKEN", "POLL_INTERVAL"):
        if key in os.environ:
            cfg[key] = os.environ[key]

    return cfg


def _get_config() -> tuple:
    """Return (salesman_url, api_token). Raises ValueError if either is missing."""
    cfg = _load_config()
    url = cfg.get("SALESMAN_URL", "").rstrip("/")
    token = cfg.get("ARTIST_API_TOKEN", "")
    if not url:
        raise ValueError(
            "SALESMAN_URL not set. Add it to .salesman_config or set the env var."
        )
    if not token:
        raise ValueError(
            "ARTIST_API_TOKEN not set. Add it to .salesman_config or set the env var."
        )
    return url, token


def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """
    Make an authenticated request to the Salesman API.
    Logs all calls; never logs the Bearer token.
    Logs X-Request-Id from every response for traceability.
    Returns parsed JSON dict. Raises SalesmanAPIError on non-2xx.
    """
    url, token = _get_config()
    full_url = url + path

    logger.info("%s %s", method, full_url)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None

    req = urllib.request.Request(full_url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            request_id = resp.headers.get("X-Request-Id", "")
            raw = resp.read().decode()
            logger.info(
                "  -> %s X-Request-Id=%s", resp.status, request_id
            )
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        request_id = e.headers.get("X-Request-Id", "") if e.headers else ""
        body_text = e.read().decode(errors="replace")
        logger.warning(
            "  -> HTTP %s X-Request-Id=%s body=%s",
            e.code,
            request_id,
            body_text[:200],
        )
        raise SalesmanAPIError(e.code, body_text, request_id) from e


def get_incoming() -> Optional[dict]:
    """
    GET /salesman/orders/incoming?status=new&limit=1
    Returns the next pending order dict, or None if the queue is empty.
    Raises SalesmanAPIError on auth/server errors.
    """
    result = _request("GET", "/salesman/orders/incoming?status=new&limit=1")
    # Support {"items": [...]}, {"orders": [...]}, or a bare list
    if isinstance(result, list):
        return result[0] if result else None
    for key in ("items", "orders", "data"):
        orders = result.get(key)
        if orders:
            return orders[0]
    return None


def claim(order_id: str, idempotency_key: str) -> dict:
    """
    POST /salesman/orders/:id/claim
    Raises SalesmanAPIError(409) if another poller already claimed it.
    """
    return _request(
        "POST",
        f"/salesman/orders/{order_id}/claim",
        {"idempotency_key": idempotency_key},
    )


def ack(order_id: str) -> dict:
    """POST /salesman/orders/:id/ack"""
    return _request("POST", f"/salesman/orders/{order_id}/ack")


def complete(order_id: str, video_url: str = "", notes: str = "") -> dict:
    """POST /salesman/orders/:id/complete with YouTube proof-of-work payload."""
    body: dict = {"result": {"note": notes or "Artwork completed"}}

    if video_url:
        # Normalize to canonical YouTube watch URL and send field names expected by Salesman API.
        video_id = video_url.split("v=")[-1] if "v=" in video_url else video_url.split("/")[-1]
        canonical_url = f"https://youtube.com/watch?v={video_id}"
        body["result"].update({
            "proofType": "youtube",
            "proofUrl": canonical_url,          # legacy compatibility
            "proofOfWorkUrl": canonical_url,    # required by current Salesman API
            "proofMeta": {"videoId": video_id},
        })
        body["proofOfWorkUrl"] = canonical_url

    return _request("POST", f"/salesman/orders/{order_id}/complete", body)


def fail(order_id: str, reason: str, retryable: bool = True) -> dict:
    """POST /salesman/orders/:id/fail"""
    return _request(
        "POST",
        f"/salesman/orders/{order_id}/fail",
        {"reason": reason, "retryable": retryable},
    )
