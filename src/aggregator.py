"""
Ties baseline + rules together into a single investigation report.

This is the only place that decides the overall verdict, and it does so
explicitly: "no_concerns" is a deliberate conclusion the system states, not
just the absence of output.
"""

from src.baseline import compute_baseline, save_baseline
from src.rules import run_all_rules
from src.ai_narrative import generate_narrative

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def load_transactions(conn, customer_id):
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT t.txn_id, t.customer_id, t.txn_date, t.txn_time, t.amount, t.channel,
               t.description, t.raw_row_ref, t.payee_id,
               p.payee_name, p.first_seen_date AS payee_first_seen
        FROM transactions t
        LEFT JOIN payees p ON t.payee_id = p.payee_id
        WHERE t.customer_id = %s
        ORDER BY t.txn_date, t.txn_time
        """,
        (customer_id,),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def build_report(transactions, config):
    """Pure function: transactions + config -> report dict. No DB access."""
    baseline = compute_baseline(transactions)
    findings = run_all_rules(transactions, baseline, config)

    txn_lookup = {t["txn_id"]: t for t in transactions}

    def txn_detail(txn_id):
        t = txn_lookup[txn_id]
        return {
            "txn_id": t["txn_id"],
            "date": str(t["txn_date"]),
            "time": str(t["txn_time"]),
            "amount": float(t["amount"]),
            "channel": t["channel"],
            "payee": t.get("payee_name") or "(no payee on record)",
            "description": t.get("description") or "",
        }

    enriched_findings = []
    for f in findings:
        enriched_findings.append({
            "rule_code": f["rule_code"],
            "severity": f["severity"],
            "summary": f["summary"],
            "how_it_differs": f["how_it_differs"],
            "first_step": f["first_step"],
            "transactions": [txn_detail(tid) for tid in f["txn_ids"]],
        })

    enriched_findings.sort(key=lambda f: -SEVERITY_RANK.get(f["severity"], 0))

    overall_verdict = "review_recommended" if enriched_findings else "no_concerns"

    report = {
        "overall_verdict": overall_verdict,
        "headline": (
            "No activity in this history meets any of the configured risk criteria. "
            "This account shows routine, consistent behaviour and does not currently warrant investigator review."
            if overall_verdict == "no_concerns"
            else f"{len(enriched_findings)} item(s) in this history warrant a closer look. See findings below."
        ),
        "baseline_summary": {
            "avg_amount": baseline["avg_amount"],
            "stddev_amount": baseline["stddev_amount"],
            "median_amount": baseline["median_amount"],
            "typical_hours": f"{baseline['typical_hour_start']:02d}:00-{baseline['typical_hour_end']:02d}:00",
            "typical_channels": sorted(baseline["typical_channels"]),
            "sample_size": baseline["sample_size"],
        },
        "findings": enriched_findings,
        "transactions_reviewed": len(transactions),
    }
    return report, baseline


def persist_investigation(conn, customer_id, report, baseline):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO investigations (customer_id, overall_verdict, ai_narrative, ai_narrative_source)
           VALUES (%s, %s, %s, %s)""",
        (customer_id, report["overall_verdict"], report.get("ai_narrative"), report.get("ai_narrative_source")),
    )
    investigation_id = cur.lastrowid

    for f in report["findings"]:
        cur.execute(
            """
            INSERT INTO findings (investigation_id, rule_code, severity, summary_text,
                                   how_it_differs_text, first_step_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (investigation_id, f["rule_code"], f["severity"], f["summary"],
             f["how_it_differs"], f["first_step"]),
        )
        finding_id = cur.lastrowid
        for t in f["transactions"]:
            cur.execute(
                "INSERT INTO finding_transactions (finding_id, txn_id) VALUES (%s, %s)",
                (finding_id, t["txn_id"]),
            )

    conn.commit()
    cur.close()
    return investigation_id


def run_investigation(conn, customer_id, config):
    transactions = load_transactions(conn, customer_id)
    report, baseline = build_report(transactions, config)
    narrative, narrative_source = generate_narrative(report)
    report["ai_narrative"] = narrative
    report["ai_narrative_source"] = narrative_source  # "ai" or "fallback"
    save_baseline(conn, customer_id, baseline)
    investigation_id = persist_investigation(conn, customer_id, report, baseline)
    report["investigation_id"] = investigation_id
    report["customer_id"] = customer_id
    return report
