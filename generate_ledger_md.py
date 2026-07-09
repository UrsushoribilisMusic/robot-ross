#!/usr/bin/env python3
"""
generate_ledger_md.py
---------------------
Reads orders.xlsx and writes LEDGER.md — a model-readable summary with:
  - Full job table
  - Statistics (totals, success rate, by type, by buyer)
  - MTBF (Mean Time Between Failures)
  - Turnaround time stats
  - Recent activity

Run any time you want to refresh LEDGER.md:
    python generate_ledger_md.py
"""

import os, sys, json
from datetime import datetime, timedelta
from collections import defaultdict, Counter

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl not installed — run: pip install openpyxl")

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ORDERS_FILE = os.path.join(SCRIPT_DIR, "skills", "robot-ross", "orders.xlsx")
OUT_FILE    = os.path.join(SCRIPT_DIR, "LEDGER.md")
ATF_COPY    = os.path.join(SCRIPT_DIR, "..", "atf-review", "ATF", "artifacts", "ledger", "LEDGER.md")


# ── Load data ─────────────────────────────────────────────────────────────────

def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return []
    wb = openpyxl.load_workbook(ORDERS_FILE, data_only=True)
    ws = wb.active
    orders = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        received, buyer, order_type, content, produced, status, video_url, posted, shipped = \
            (row[i] if i < len(row) else None for i in range(9))
        orders.append({
            "received":   received,
            "buyer":      buyer or "",
            "type":       order_type or "",
            "content":    content or "",
            "produced":   produced,
            "status":     status or "",
            "video_url":  video_url or "",
            "posted":     posted or "",
            "shipped":    shipped or "",
        })
    return orders


def parse_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(val), fmt)
        except ValueError:
            pass
    return None


# ── Statistics ────────────────────────────────────────────────────────────────

def compute_stats(orders):
    total     = len(orders)
    successes = [o for o in orders if o["status"] == "success"]
    failures  = [o for o in orders if o["status"] in ("failure", "failed")]
    in_prog   = [o for o in orders if o["status"] == "in_progress"]
    cancelled = [o for o in orders if o["status"] not in ("success","failure","failed","in_progress","")]

    # Turnaround times (received → produced) for completed jobs
    turnarounds = []
    for o in successes:
        r = parse_dt(o["received"])
        p = parse_dt(o["produced"])
        if r and p and p > r:
            turnarounds.append((p - r).total_seconds())

    avg_tt  = sum(turnarounds) / len(turnarounds) if turnarounds else None
    min_tt  = min(turnarounds) if turnarounds else None
    max_tt  = max(turnarounds) if turnarounds else None

    # MTBF: average time between consecutive failures
    failure_times = sorted(
        [parse_dt(o["received"]) for o in failures if parse_dt(o["received"])],
        key=lambda x: x
    )
    mtbf_secs = None
    if len(failure_times) >= 2:
        gaps = [(failure_times[i+1] - failure_times[i]).total_seconds()
                for i in range(len(failure_times)-1)]
        mtbf_secs = sum(gaps) / len(gaps)

    # By type
    by_type   = Counter(o["type"] for o in orders)
    # By buyer
    by_buyer  = Counter(o["buyer"] for o in orders if o["buyer"])
    # Success rate by type
    sr_by_type = {}
    for t in by_type:
        t_orders = [o for o in orders if o["type"] == t]
        t_succ   = sum(1 for o in t_orders if o["status"] == "success")
        sr_by_type[t] = (t_succ, len(t_orders))

    # Daily job counts (last 30 days)
    cutoff = datetime.now() - timedelta(days=30)
    daily  = defaultdict(int)
    for o in orders:
        r = parse_dt(o["received"])
        if r and r >= cutoff:
            daily[r.strftime("%Y-%m-%d")] += 1

    # Streak: consecutive days with at least one job
    streak = 0
    day = datetime.now().date()
    while True:
        if daily.get(str(day), 0) > 0:
            streak += 1
            day -= timedelta(days=1)
        else:
            break

    return {
        "total":        total,
        "successes":    len(successes),
        "failures":     len(failures),
        "in_progress":  len(in_prog),
        "cancelled":    len(cancelled),
        "success_rate": len(successes) / total * 100 if total else 0,
        "avg_tt_secs":  avg_tt,
        "min_tt_secs":  min_tt,
        "max_tt_secs":  max_tt,
        "mtbf_secs":    mtbf_secs,
        "by_type":      dict(by_type),
        "by_buyer":     dict(by_buyer.most_common(10)),
        "sr_by_type":   sr_by_type,
        "daily_last30": dict(sorted(daily.items())),
        "streak_days":  streak,
        "with_video":   sum(1 for o in orders if o["video_url"]),
        "posted_count": sum(1 for o in orders if o["posted"]),
        "shipped_count":sum(1 for o in orders if o["shipped"]),
    }


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_dur(secs):
    if secs is None:
        return "—"
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"

def fmt_dt(val):
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M")
    return str(val)[:16]

def status_icon(s):
    return {"success":"✅","failure":"❌","failed":"❌","in_progress":"⏳"}.get(s, "❓")

def clean_cell(s):
    """Replace newlines/tabs so they don't break Markdown table rows."""
    return str(s).replace("\n", " ").replace("\r", "").replace("|", "\\|").strip()


# ── Markdown builder ─────────────────────────────────────────────────────────

def build_md(orders, stats, generated_at):
    lines = []
    A = lines.append

    A(f"# Robot Ross — Operational Ledger")
    A(f"")
    A(f"> Auto-generated {generated_at}  ")
    A(f"> Source: `skills/robot-ross/orders.xlsx`  ")
    A(f"> Refresh: `python generate_ledger_md.py`")
    A(f"")

    # ── Summary dashboard ──
    A(f"## Summary Dashboard")
    A(f"")
    A(f"| Metric | Value |")
    A(f"|--------|-------|")
    A(f"| Total jobs | **{stats['total']}** |")
    A(f"| Successful | ✅ {stats['successes']} |")
    A(f"| Failed | ❌ {stats['failures']} |")
    A(f"| In progress | ⏳ {stats['in_progress']} |")
    A(f"| Success rate | **{stats['success_rate']:.1f}%** |")
    A(f"| Avg turnaround | {fmt_dur(stats['avg_tt_secs'])} |")
    A(f"| Fastest job | {fmt_dur(stats['min_tt_secs'])} |")
    A(f"| Slowest job | {fmt_dur(stats['max_tt_secs'])} |")
    A(f"| MTBF | {fmt_dur(stats['mtbf_secs'])} |")
    A(f"| Jobs with video | {stats['with_video']} |")
    A(f"| Posted | {stats['posted_count']} |")
    A(f"| Shipped | {stats['shipped_count']} |")
    A(f"| Active streak | {stats['streak_days']} day(s) |")
    A(f"")

    # ── By type ──
    A(f"## Jobs by Type")
    A(f"")
    A(f"| Type | Total | Successes | Failures | Success Rate |")
    A(f"|------|-------|-----------|----------|--------------|")
    for t, (succ, tot) in sorted(stats["sr_by_type"].items(), key=lambda x: -x[1][1]):
        fail = tot - succ
        rate = succ / tot * 100 if tot else 0
        A(f"| `{t}` | {tot} | {succ} | {fail} | {rate:.0f}% |")
    A(f"")

    # ── By buyer ──
    if stats["by_buyer"]:
        A(f"## Top Buyers")
        A(f"")
        A(f"| Buyer | Jobs |")
        A(f"|-------|------|")
        for buyer, count in stats["by_buyer"].items():
            A(f"| {buyer or '*(walk-in)*'} | {count} |")
        A(f"")

    # ── Activity last 30 days ──
    if stats["daily_last30"]:
        A(f"## Activity — Last 30 Days")
        A(f"")
        A(f"| Date | Jobs |")
        A(f"|------|------|")
        for date, count in sorted(stats["daily_last30"].items(), reverse=True):
            bar = "█" * count
            A(f"| {date} | {bar} {count} |")
        A(f"")

    # ── MTBF note ──
    A(f"## Reliability Notes")
    A(f"")
    if stats["failures"] == 0:
        A(f"- No failures recorded. MTBF cannot be computed (no failures to measure between).")
    elif stats["failures"] == 1:
        A(f"- Only one failure recorded. MTBF requires at least two failures to compute a gap.")
    else:
        A(f"- **MTBF**: {fmt_dur(stats['mtbf_secs'])} — average time between consecutive failures.")
        A(f"- Based on {stats['failures']} failure events.")
    A(f"- Success rate: **{stats['success_rate']:.1f}%** across {stats['total']} total jobs.")
    if stats["in_progress"] > 0:
        A(f"- **{stats['in_progress']} jobs stuck as `in_progress`** — these are likely stale rows from "
          f"sessions that crashed before `order_log.end()` was called. They are excluded from "
          f"turnaround time calculations.")
    A(f"")

    # ── Recent jobs (last 10) ──
    A(f"## Recent Jobs (last 10)")
    A(f"")
    A(f"| # | Received | Buyer | Type | Content | Duration | Status | Video | Posted |")
    A(f"|---|----------|-------|------|---------|----------|--------|-------|--------|")
    recent = orders[-10:][::-1]  # newest first
    for i, o in enumerate(recent, 1):
        r   = parse_dt(o["received"])
        p   = parse_dt(o["produced"])
        dur = fmt_dur((p - r).total_seconds()) if r and p and p > r else "—"
        vid = f"[▶]({o['video_url']})" if o["video_url"] else ""
        content_short = clean_cell(o["content"])
        if len(content_short) > 35: content_short = content_short[:35] + "…"
        A(f"| {len(orders)-i+1} | {fmt_dt(o['received'])} | {o['buyer'] or '—'} | "
          f"`{o['type']}` | {content_short} | {dur} | "
          f"{status_icon(o['status'])} {o['status']} | {vid} | {o['posted'] or ''} |")
    A(f"")


    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"Reading {ORDERS_FILE}…")
    orders = load_orders()

    if not orders:
        print("No orders found — writing empty ledger.")

    stats = compute_stats(orders)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = build_md(orders, stats, generated_at)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Written: {OUT_FILE}")

    # Sync to ATF QA corpus
    atf_path = os.path.normpath(ATF_COPY)
    if os.path.isdir(os.path.dirname(atf_path)):
        import shutil
        shutil.copy2(OUT_FILE, atf_path)
        print(f"Synced:  {atf_path}")
    else:
        print(f"(ATF path not found — skipping sync: {atf_path})")

    print(f"  {stats['total']} jobs · {stats['successes']} success · {stats['failures']} failures")
    print(f"  Success rate: {stats['success_rate']:.1f}%")
    if stats["mtbf_secs"]:
        print(f"  MTBF: {fmt_dur(stats['mtbf_secs'])}")


if __name__ == "__main__":
    main()
