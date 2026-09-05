"""
Generates synthetic customer histories for demo/testing purposes and loads
them into MySQL (schema.sql must already be applied).

Run directly:  python seed_data.py

Also exposes build_synthetic_customers() which returns pure Python data
structures (no DB needed) - used by tests/test_rules_dry_run.py to validate
rule logic without a live database.
"""

import random
from datetime import date, time, timedelta

random.seed(42)

START = date(2026, 6, 1)
END = date(2026, 9, 30)
OLD_PAYEE_FIRST_SEEN = date(2024, 1, 1)


def _daterange_days():
    days = (END - START).days
    return [START + timedelta(days=i) for i in range(days + 1)]


def _routine_transactions(customer_key):
    """Common, unremarkable monthly pattern shared by all synthetic customers."""
    txns = []
    d = START.replace(day=1)
    month_starts = []
    cur = d
    while cur <= END:
        month_starts.append(cur)
        # advance to next month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    for m_start in month_starts:
        # Salary credit on the 1st
        txns.append({
            "txn_date": m_start, "txn_time": time(9, 5),
            "amount": 75000.00, "channel": "NETBANKING",
            "payee_name": "Employer Pvt Ltd", "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
            "description": "Monthly salary credit",
        })
        # Rent on the 3rd
        rent_day = min(m_start.day + 2, 28)
        txns.append({
            "txn_date": m_start.replace(day=rent_day), "txn_time": time(10, 30),
            "amount": 20000.00, "channel": "NETBANKING",
            "payee_name": "Landlord - Ramesh", "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
            "description": "Monthly rent",
        })
        # Utility bill
        util_day = min(m_start.day + 6, 28)
        txns.append({
            "txn_date": m_start.replace(day=util_day), "txn_time": time(19, 0),
            "amount": round(random.uniform(900, 2800), 2), "channel": "UPI",
            "payee_name": "Electricity Board", "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
            "description": "Electricity bill",
        })
        # Subscription
        sub_day = min(m_start.day + 9, 28)
        txns.append({
            "txn_date": m_start.replace(day=sub_day), "txn_time": time(8, 15),
            "amount": 499.00, "channel": "DEBIT_CARD",
            "payee_name": "Streaming Service", "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
            "description": "Subscription renewal",
        })
        # Groceries, ~2x/week
        day_cursor = m_start
        month_end = (month_starts[month_starts.index(m_start) + 1] - timedelta(days=1)
                     if m_start != month_starts[-1] else END)
        while day_cursor <= month_end:
            if day_cursor.weekday() in (1, 4):  # Tue/Fri
                hour = random.randint(10, 20)
                minute = random.randint(0, 59)
                txns.append({
                    "txn_date": day_cursor, "txn_time": time(hour, minute),
                    "amount": round(random.uniform(300, 1500), 2), "channel": "UPI",
                    "payee_name": random.choice(["BigBasket", "Local Grocery Store"]),
                    "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
                    "description": "Groceries",
                })
            day_cursor += timedelta(days=1)
        # Occasional ATM withdrawal
        if random.random() < 0.6:
            atm_day = min(m_start.day + 15, 28)
            txns.append({
                "txn_date": m_start.replace(day=atm_day), "txn_time": time(random.randint(11, 18), 0),
                "amount": round(random.choice([2000, 3000, 4000, 5000]), 2), "channel": "ATM",
                "payee_name": "Cash Withdrawal", "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
                "description": "ATM withdrawal",
            })

    return txns


def build_synthetic_customers():
    """Returns dict: customer_name -> (account_opened_date, list of txn dicts)."""
    customers = {}

    # 1. Clean / routine customer - no anomalies at all
    clean_txns = _routine_transactions("anitha")
    customers["Balavignesh"] = (date(2023, 3, 10), clean_txns)

    # 2. One unusually large transfer, otherwise routine
    vikram_txns = _routine_transactions("vikram") + [{
        "txn_date": date(2026, 8, 14), "txn_time": time(15, 40),
        "amount": 500000.00, "channel": "NETBANKING",
        "payee_name": "Landlord - Ramesh",  # uses an existing, normal channel/payee on purpose
        "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
        "description": "Large one-off transfer",
    }]
    customers["Deepak"] = (date(2022, 7, 1), vikram_txns)

    # 3. Multiple rule triggers: new payee burst, odd hours, pattern break
    priya_base = _routine_transactions("priya")
    new_payee_first_seen = date(2026, 9, 25)
    burst = [
        {
            "txn_date": date(2026, 9, 25), "txn_time": time(21, 10),
            "amount": 18000.00, "channel": "UPI",
            "payee_name": "QuickCash Transfers", "payee_first_seen": new_payee_first_seen,
            "description": "Transfer",
        },
        {
            "txn_date": date(2026, 9, 26), "txn_time": time(9, 5),
            "amount": 22000.00, "channel": "UPI",
            "payee_name": "QuickCash Transfers", "payee_first_seen": new_payee_first_seen,
            "description": "Transfer",
        },
        {
            "txn_date": date(2026, 9, 26), "txn_time": time(23, 40),
            "amount": 15500.00, "channel": "UPI",
            "payee_name": "QuickCash Transfers", "payee_first_seen": new_payee_first_seen,
            "description": "Transfer",
        },
        {
            "txn_date": date(2026, 9, 27), "txn_time": time(20, 0),
            "amount": 25000.00, "channel": "UPI",
            "payee_name": "QuickCash Transfers", "payee_first_seen": new_payee_first_seen,
            "description": "Transfer",
        },
    ]
    odd_hour_txn = [{
        "txn_date": date(2026, 9, 12), "txn_time": time(3, 15),
        "amount": 2000.00, "channel": "UPI",
        "payee_name": "Local Grocery Store", "payee_first_seen": OLD_PAYEE_FIRST_SEEN,
        "description": "Late night payment",
    }]
    pattern_break_txn = [{
        "txn_date": date(2026, 9, 20), "txn_time": time(14, 0),
        "amount": 80000.00, "channel": "WIRE_TRANSFER",
        "payee_name": "Overseas Trading Co", "payee_first_seen": date(2026, 9, 20),
        "description": "Wire transfer",
    }]
    priya_txns = priya_base + burst + odd_hour_txn + pattern_break_txn
    customers["Dhayaanithi"] = (date(2021, 11, 20), priya_txns)

    return customers


# ---------------------------------------------------------------------
# MySQL loading
# ---------------------------------------------------------------------

def load_into_mysql():
    from src.db import get_connection

    conn = get_connection()
    cur = conn.cursor()

    # Clean slate for a repeatable demo
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for tbl in ["finding_transactions", "findings", "investigations",
                "customer_baseline", "transactions", "payees", "customers"]:
        cur.execute(f"DELETE FROM {tbl}")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.commit()

    customers = build_synthetic_customers()

    for name, (opened_date, txns) in customers.items():
        cur.execute(
            "INSERT INTO customers (full_name, account_opened_date) VALUES (%s, %s)",
            (name, opened_date),
        )
        customer_id = cur.lastrowid

        payee_ids = {}
        for t in txns:
            pname = t["payee_name"]
            if pname not in payee_ids:
                cur.execute(
                    """INSERT INTO payees (customer_id, payee_name, first_seen_date)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE first_seen_date = first_seen_date""",
                    (customer_id, pname, t["payee_first_seen"]),
                )
                cur.execute(
                    "SELECT payee_id FROM payees WHERE customer_id=%s AND payee_name=%s",
                    (customer_id, pname),
                )
                payee_ids[pname] = cur.fetchone()[0]

        for t in sorted(txns, key=lambda x: (x["txn_date"], x["txn_time"])):
            cur.execute(
                """INSERT INTO transactions
                       (customer_id, payee_id, txn_date, txn_time, amount, channel, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (customer_id, payee_ids[t["payee_name"]], t["txn_date"], t["txn_time"],
                 t["amount"], t["channel"], t["description"]),
            )

        print(f"Loaded {len(txns)} transactions for {name} (customer_id={customer_id})")

    conn.commit()
    cur.close()
    conn.close()
    print("Seed data load complete.")


if __name__ == "__main__":
    load_into_mysql()
