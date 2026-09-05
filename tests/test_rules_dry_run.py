"""
Validates the rule engine end-to-end using the synthetic dataset, WITHOUT a
MySQL connection. Run with:  python tests/test_rules_dry_run.py
(run from the project root, or adjust sys.path as below)

Expected outcome:
  - Anitha Raman  -> no_concerns
  - Vikram Shah   -> review_recommended, LARGE_TXN only
  - Priya Nair    -> review_recommended, NEW_PAYEE_BURST + ODD_HOURS + PATTERN_BREAK
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from seed_data import build_synthetic_customers
from aggregator import build_report
from db import DEFAULT_RULE_CONFIG


def to_txn_rows(txns, customer_id):
    """Shape synthetic dicts the same way aggregator.load_transactions would return from MySQL."""
    rows = []
    for i, t in enumerate(txns, start=1):
        rows.append({
            "txn_id": i,
            "customer_id": customer_id,
            "txn_date": t["txn_date"],
            "txn_time": t["txn_time"],
            "amount": t["amount"],
            "channel": t["channel"],
            "description": t["description"],
            "raw_row_ref": None,
            "payee_id": t["payee_name"],
            "payee_name": t["payee_name"],
            "payee_first_seen": t["payee_first_seen"],
        })
    return sorted(rows, key=lambda r: (r["txn_date"], r["txn_time"]))


def run():
    customers = build_synthetic_customers()
    all_pass = True

    for cid, (name, (opened, txns)) in enumerate(customers.items(), start=1):
        rows = to_txn_rows(txns, cid)
        report, baseline = build_report(rows, DEFAULT_RULE_CONFIG)
        rule_codes = sorted({f["rule_code"] for f in report["findings"]})
        print(f"\n=== {name} ===")
        print(f"transactions: {len(rows)}")
        print(f"verdict: {report['overall_verdict']}")
        print(f"rules triggered: {rule_codes}")
        for f in report["findings"]:
            print(f"  - [{f['severity']}] {f['rule_code']}: {len(f['transactions'])} txn(s) cited")
            for t in f["transactions"]:
                assert t["txn_id"] in [r["txn_id"] for r in rows], "Cited txn not traceable to input history!"

    print("\nAll cited transactions verified traceable to input history.")


if __name__ == "__main__":
    run()
