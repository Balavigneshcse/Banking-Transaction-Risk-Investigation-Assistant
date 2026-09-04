"""
Risk rules.

Design contract, deliberately strict:
  - Each rule is a pure function: (transactions, baseline, config) -> list[finding]
  - A rule NEVER states that fraud occurred. It states what pattern was
    observed, which transactions support it, and how that differs from the
    customer's own established behaviour.
  - Every finding carries the exact txn_ids behind it, so the report layer
    can never say more than the data supports.
"""

from datetime import datetime, timedelta, time as dt_time
from collections import defaultdict


def _dt(txn):
    """Combine txn_date + txn_time into a single datetime for windowing math."""
    t = txn["txn_time"]
    # MySQL connector returns TIME columns as timedelta; convert to time
    if isinstance(t, timedelta):
        total_seconds = int(t.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        t = dt_time(hours, minutes, seconds)
    return datetime.combine(txn["txn_date"], t)


def _get_hour(txn_time):
    """Extract hour from a time or timedelta object."""
    if isinstance(txn_time, timedelta):
        return int(txn_time.total_seconds()) // 3600
    if hasattr(txn_time, 'hour'):
        return txn_time.hour
    return int(str(txn_time).split(':')[0])


def _severity_from_z(z):
    if z >= 6:
        return "high"
    if z >= 4:
        return "medium"
    return "low"


# ---------------------------------------------------------------------
# Rule 1: unusually large transaction(s) relative to this customer's own history
# ---------------------------------------------------------------------

def _is_established_recurring(t, transactions):
    """
    A transaction is part of the customer's own established pattern (and should
    NOT be flagged as "large") if the same payee has repeated, similarly-sized
    transactions elsewhere in the history - e.g. a monthly salary credit or rent
    payment. Large-but-routine is exactly what this guard exists to exclude.
    """
    if not t.get("payee_id") and not t.get("payee_name"):
        return False
    amount = float(t["amount"])
    similar = [
        o for o in transactions
        if o is not t
        and (o.get("payee_id") == t.get("payee_id") or o.get("payee_name") == t.get("payee_name"))
        and abs(float(o["amount"]) - amount) <= amount * 0.10
    ]
    return len(similar) >= 2


def rule_large_txn(transactions, baseline, config):
    k = config.get("LARGE_TXN_STDDEV_K", 3)
    abs_floor = config.get("LARGE_TXN_ABS_FLOOR", 50000)
    mean = baseline["avg_amount"]
    std = baseline["stddev_amount"]

    flagged = []
    for t in transactions:
        if _is_established_recurring(t, transactions):
            continue
        amount = float(t["amount"])
        if std > 0:
            z = (amount - mean) / std
        else:
            z = amount / mean if mean > 0 else 0
        threshold_hit = (std > 0 and amount > mean + k * std) or amount >= abs_floor
        if threshold_hit:
            flagged.append((t, z))

    if not flagged:
        return []

    max_z = max(z for _, z in flagged)
    severity = _severity_from_z(max_z if max_z > 0 else (flagged[0][0]["amount"] / abs_floor) * 3)

    txns_sorted = sorted(flagged, key=lambda pair: -pair[0]["amount"])
    lines = [
        f"{t['txn_date']} - Rs.{t['amount']:,.2f} to {t.get('payee_name') or 'unknown payee'} via {t['channel']}"
        for t, _ in txns_sorted
    ]
    summary = (
        f"{len(flagged)} transaction(s) are well above this customer's normal transaction size: "
        + "; ".join(lines)
    )
    how_it_differs = (
        f"This customer's typical transaction is around Rs.{mean:,.2f} "
        f"(std. dev. Rs.{std:,.2f}, based on {baseline['sample_size']} transactions on file). "
        f"The flagged transaction(s) sit far outside that range."
    )
    first_step = (
        "Confirm the purpose and destination of the largest flagged transaction with the customer "
        "and check whether the receiving account/payee has any prior adverse history."
    )

    return [{
        "rule_code": "LARGE_TXN",
        "severity": severity,
        "txn_ids": [t["txn_id"] for t, _ in flagged],
        "summary": summary,
        "how_it_differs": how_it_differs,
        "first_step": first_step,
    }]


# ---------------------------------------------------------------------
# Rule 2: burst of payments to a newly added payee
# ---------------------------------------------------------------------

def rule_new_payee_burst(transactions, baseline, config):
    window_days = config.get("NEW_PAYEE_WINDOW_DAYS", 30)
    burst_count = config.get("NEW_PAYEE_BURST_COUNT", 3)
    burst_window_hours = config.get("NEW_PAYEE_BURST_WINDOW_HOURS", 72)

    if not transactions:
        return []

    most_recent_date = max(t["txn_date"] for t in transactions)

    by_payee = defaultdict(list)
    for t in transactions:
        if t.get("payee_id") is not None:
            by_payee[t["payee_id"]].append(t)

    findings = []
    for payee_id, txns in by_payee.items():
        first_seen = txns[0].get("payee_first_seen")
        if first_seen is None:
            continue
        is_new = (most_recent_date - first_seen).days <= window_days
        if not is_new:
            continue

        txns_sorted = sorted(txns, key=_dt)
        # Slide a window and look for burst_count+ payments within burst_window_hours
        for i in range(len(txns_sorted)):
            window_start = _dt(txns_sorted[i])
            window_end = window_start + timedelta(hours=burst_window_hours)
            cluster = [t for t in txns_sorted if window_start <= _dt(t) <= window_end]
            if len(cluster) >= burst_count:
                payee_name = cluster[0].get("payee_name") or "this payee"
                total = sum(float(t["amount"]) for t in cluster)
                lines = [
                    f"{t['txn_date']} {t['txn_time']} - Rs.{t['amount']:,.2f} via {t['channel']}"
                    for t in cluster
                ]
                severity = "high" if len(cluster) >= 5 else ("medium" if len(cluster) >= 4 else "low")
                findings.append({
                    "rule_code": "NEW_PAYEE_BURST",
                    "severity": severity,
                    "txn_ids": [t["txn_id"] for t in cluster],
                    "summary": (
                        f"{len(cluster)} payments totalling Rs.{total:,.2f} were sent to '{payee_name}' "
                        f"within a {burst_window_hours}-hour window: " + "; ".join(lines)
                    ),
                    "how_it_differs": (
                        f"'{payee_name}' was first added as a payee on {first_seen}, "
                        f"only {(most_recent_date - first_seen).days} day(s) before the most recent "
                        f"activity on file. This customer does not have a history of repeated rapid "
                        f"payments to a payee this recently added."
                    ),
                    "first_step": (
                        f"Verify with the customer why '{payee_name}' was added and whether they "
                        "authorised each of these payments individually."
                    ),
                })
                break  # one finding per payee is enough; avoid duplicate overlapping windows

    return findings


# ---------------------------------------------------------------------
# Rule 3: activity at hours the customer doesn't normally transact
# ---------------------------------------------------------------------

def rule_odd_hours(transactions, baseline, config):
    buffer_hrs = config.get("ODD_HOURS_BUFFER", 1)
    start = max(0, baseline["typical_hour_start"] - buffer_hrs)
    end = min(23, baseline["typical_hour_end"] + buffer_hrs)

    flagged = []
    for t in transactions:
        hour = _get_hour(t["txn_time"])
        if hour < start or hour > end:
            flagged.append(t)

    if not flagged:
        return []

    lines = [
        f"{t['txn_date']} {t['txn_time']} - Rs.{t['amount']:,.2f} to {t.get('payee_name') or 'unknown payee'} via {t['channel']}"
        for t in flagged
    ]
    max_dev = max(
        max(start - _get_hour(t["txn_time"]), _get_hour(t["txn_time"]) - end, 0)
        for t in flagged
    )
    severity = "high" if max_dev >= 4 else ("medium" if max_dev >= 2 else "low")

    return [{
        "rule_code": "ODD_HOURS",
        "severity": severity,
        "txn_ids": [t["txn_id"] for t in flagged],
        "summary": (
            f"{len(flagged)} transaction(s) occurred outside this customer's normal active hours: "
            + "; ".join(lines)
        ),
        "how_it_differs": (
            f"Based on {baseline['sample_size']} transactions on file, this customer is normally "
            f"active between {baseline['typical_hour_start']:02d}:00 and {baseline['typical_hour_end']:02d}:00. "
            f"The flagged transaction(s) fall well outside that window."
        ),
        "first_step": (
            "Check whether the customer was travelling or has a stated reason for activity at this hour, "
            "and confirm the device/channel used matches their usual pattern."
        ),
    }]


# ---------------------------------------------------------------------
# Rule 4: transaction breaks the customer's own established pattern
# (channel they essentially never use, at a size well above their norm)
# ---------------------------------------------------------------------

def rule_pattern_break(transactions, baseline, config):
    rarity_pct = config.get("PATTERN_BREAK_CHANNEL_RARITY_PCT", 5)
    min_ratio = config.get("PATTERN_BREAK_MIN_RATIO", 1.5)
    median = baseline["median_amount"] or 0

    channel_counts = defaultdict(int)
    for t in transactions:
        channel_counts[t["channel"]] += 1
    total = sum(channel_counts.values()) or 1

    flagged = []
    for t in transactions:
        share = (channel_counts[t["channel"]] / total) * 100
        is_rare_channel = share < rarity_pct
        is_above_norm = median > 0 and float(t["amount"]) >= median * min_ratio
        if is_rare_channel and is_above_norm:
            flagged.append(t)

    if not flagged:
        return []

    lines = [
        f"{t['txn_date']} - Rs.{t['amount']:,.2f} via {t['channel']} to {t.get('payee_name') or 'unknown payee'}"
        for t in flagged
    ]
    max_ratio = max(float(t["amount"]) / median for t in flagged) if median else 1
    severity = "high" if max_ratio >= 3 else ("medium" if max_ratio >= 1.5 else "low")

    return [{
        "rule_code": "PATTERN_BREAK",
        "severity": severity,
        "txn_ids": [t["txn_id"] for t in flagged],
        "summary": (
            f"{len(flagged)} transaction(s) used a channel this customer rarely uses, at a size above "
            f"their typical transaction: " + "; ".join(lines)
        ),
        "how_it_differs": (
            f"This customer's median transaction is Rs.{median:,.2f}, and the channel(s) involved here "
            f"account for less than {rarity_pct}% of their historical transactions."
        ),
        "first_step": (
            "Confirm the customer initiated this channel switch themselves (e.g. recent card/account "
            "changes, new device) before treating it as routine."
        ),
    }]


ALL_RULES = [rule_large_txn, rule_new_payee_burst, rule_odd_hours, rule_pattern_break]


def run_all_rules(transactions, baseline, config):
    findings = []
    for rule_fn in ALL_RULES:
        findings.extend(rule_fn(transactions, baseline, config))
    return findings
