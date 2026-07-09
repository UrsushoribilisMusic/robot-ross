# Robot Ross — Operational Ledger

> Auto-generated 2026-04-15 10:50:36  
> Source: `skills/robot-ross/orders.xlsx`  
> Refresh: `python generate_ledger_md.py`

## Summary Dashboard

| Metric | Value |
|--------|-------|
| Total jobs | **23** |
| Successful | ✅ 15 |
| Failed | ❌ 1 |
| In progress | ⏳ 7 |
| Success rate | **65.2%** |
| Avg turnaround | 2m 28s |
| Fastest job | 1m 39s |
| Slowest job | 3m 5s |
| MTBF | — |
| Jobs with video | 16 |
| Posted | 0 |
| Shipped | 0 |
| Active streak | 0 day(s) |

## Jobs by Type

| Type | Total | Successes | Failures | Success Rate |
|------|-------|-----------|----------|--------------|
| `write` | 14 | 12 | 2 | 86% |
| `svg` | 8 | 2 | 6 | 25% |
| `sketch` | 1 | 1 | 0 | 100% |

## Top Buyers

| Buyer | Jobs |
|-------|------|
| Miguel | 8 |
| miguel+test@bigbearengineering.com | 1 |
| shopify-order-1002 | 1 |
| John | 1 |
| Rodriguez | 1 |

## Reliability Notes

- Only one failure recorded. MTBF requires at least two failures to compute a gap.
- Success rate: **65.2%** across 23 total jobs.
- **7 jobs stuck as `in_progress`** — these are likely stale rows from sessions that crashed before `order_log.end()` was called. They are excluded from turnaround time calculations.

## Recent Jobs (last 10)

| # | Received | Buyer | Type | Content | Duration | Status | Video | Posted |
|---|----------|-------|------|---------|----------|--------|-------|--------|
| 23 | 2026-02-25 17:40 | Miguel | `sketch` | Draw me a bunny and a bear | 2m 8s | ✅ success | [▶](https://www.youtube.com/watch?v=lQludLHn_Og) |  |
| 22 | 2026-02-25 17:29 | Miguel | `svg` | Draw a Bunny and a Bear | 1m 8s | ❌ failed | [▶](https://www.youtube.com/watch?v=Bh6Gg-otujU) |  |
| 21 | 2026-02-25 17:18 | Miguel | `write` | a teddy and a bunny | 1m 51s | ✅ success | [▶](https://www.youtube.com/watch?v=GuMlCxCTGyM) |  |
| 20 | 2026-02-25 17:02 | Miguel | `write` | Shopify order 7440915890513 | 2m 48s | ✅ success | [▶](https://www.youtube.com/watch?v=jbvHctvfEQk) |  |
| 19 | 2026-02-25 16:25 | Miguel | `write` | Shopify order 7440842162513 | 2m 18s | ✅ success | [▶](https://www.youtube.com/watch?v=jl1pacZYdic) |  |
| 18 | 2026-02-25 16:19 | Miguel | `write` | Shopify order 7440834494801 | 2m 53s | ✅ success | [▶](https://www.youtube.com/watch?v=qzVWjsUHGlU) |  |
| 17 | 2026-02-25 14:57 | Miguel | `write` | Shopify order 7440676061521 | 2m 45s | ✅ success | [▶](https://www.youtube.com/watch?v=geV66AkEA3U) |  |
| 16 | 2026-02-25 14:45 | Miguel | `write` | Shopify order 7440630546769 | 2m 47s | ✅ success | [▶](https://www.youtube.com/watch?v=bq9jMtgJC4A) |  |
| 15 | 2026-02-24 18:01 | Rodriguez | `write` | Shopify order 7439027110225 | 2m 17s | ✅ success | [▶](https://www.youtube.com/watch?v=jRQQUxaD3h0) |  |
| 14 | 2026-02-24 17:57 | John | `write` | Shopify order 820982911946154500 | — | ⏳ in_progress |  |  |
