"""
Builds a per-customer baseline profile: "what does normal look like for this
person" - computed purely from their own transaction history. Every risk rule
that talks about "breaking the customer's own pattern" reads from this
baseline instead of a global/one-size-fits-all threshold.
"""

import statistics
from datetime import timedelta
from collections import Counter


def _hour_of(txn):
    t = txn["txn_time"]
    if isinstance(t, timedelta):
        return int(t.total_seconds()) // 3600
    if hasattr(t, "hour"):
        return t.hour
    return int(str(t).split(":")[0])


def compute_baseline(transactions):
    """
    transactions: list of dicts with at least amount (float), txn_time, channel.
    Returns a baseline dict. Falls back to permissive defaults when history is
    too small to say anything meaningful (avoids flagging brand-new customers
    just because they don't have enough history yet).
    """
    if not transactions:
        return {
            "avg_amount": 0.0,
            "stddev_amount": 0.0,
            "median_amount": 0.0,
            "typical_hour_start": 0,
            "typical_hour_end": 23,
            "typical_channels": set(),
            "median_monthly_volume": 0,
            "sample_size": 0,
        }

    amounts = [float(t["amount"]) for t in transactions]
    hours = sorted(_hour_of(t) for t in transactions)

    avg_amount = statistics.mean(amounts)
    stddev_amount = statistics.pstdev(amounts) if len(amounts) > 1 else 0.0
    median_amount = statistics.median(amounts)

    # Typical active window = 10th to 90th percentile of historical hours,
    # widened to a minimum 6-hour span so a very regular customer (e.g. only
    # ever transacts at noon) doesn't get an unrealistically narrow window.
    n = len(hours)
    lo_idx = max(0, int(n * 0.10))
    hi_idx = min(n - 1, int(n * 0.90))
    typical_hour_start = hours[lo_idx]
    typical_hour_end = hours[hi_idx]
    if typical_hour_end - typical_hour_start < 6:
        pad = (6 - (typical_hour_end - typical_hour_start)) // 2 + 1
        typical_hour_start = max(0, typical_hour_start - pad)
        typical_hour_end = min(23, typical_hour_end + pad)

    # Channels used often enough to count as "normal" for this customer.
    channel_counts = Counter(t["channel"] for t in transactions)
    total = sum(channel_counts.values())
    typical_channels = {
        ch for ch, cnt in channel_counts.items() if (cnt / total) * 100 >= 5
    }

    # Rough median monthly transaction volume, for investigator context.
    months = Counter((t["txn_date"].year, t["txn_date"].month) for t in transactions)
    median_monthly_volume = int(statistics.median(months.values())) if months else 0

    return {
        "avg_amount": round(avg_amount, 2),
        "stddev_amount": round(stddev_amount, 2),
        "median_amount": round(median_amount, 2),
        "typical_hour_start": typical_hour_start,
        "typical_hour_end": typical_hour_end,
        "typical_channels": typical_channels,
        "median_monthly_volume": median_monthly_volume,
        "sample_size": len(transactions),
    }


def save_baseline(conn, customer_id, baseline):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO customer_baseline
            (customer_id, avg_txn_amount, stddev_txn_amount, median_txn_amount,
             typical_hour_start, typical_hour_end, typical_channels, median_monthly_volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            avg_txn_amount = VALUES(avg_txn_amount),
            stddev_txn_amount = VALUES(stddev_txn_amount),
            median_txn_amount = VALUES(median_txn_amount),
            typical_hour_start = VALUES(typical_hour_start),
            typical_hour_end = VALUES(typical_hour_end),
            typical_channels = VALUES(typical_channels),
            median_monthly_volume = VALUES(median_monthly_volume),
            computed_at = CURRENT_TIMESTAMP
        """,
        (
            customer_id,
            baseline["avg_amount"],
            baseline["stddev_amount"],
            baseline["median_amount"],
            baseline["typical_hour_start"],
            baseline["typical_hour_end"],
            ",".join(sorted(baseline["typical_channels"])),
            baseline["median_monthly_volume"],
        ),
    )
    conn.commit()
    cur.close()
