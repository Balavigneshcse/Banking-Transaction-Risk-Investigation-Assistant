"""
MySQL connection helper.

Reads connection settings from environment variables so credentials are never
hardcoded:

    DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

Defaults assume a local MySQL instance with the schema in
database/schema.sql already loaded.
"""

import os
import mysql.connector

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "txn_risk_assistant"),
}


def get_connection():
    """Return a new MySQL connection using dictionary cursors by default."""
    return mysql.connector.connect(**DB_CONFIG)


def fetch_rule_config(conn):
    """Load tunable rule thresholds from rule_config into a plain dict of floats/ints."""
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT config_key, config_value FROM rule_config")
    rows = cur.fetchall()
    cur.close()

    config = {}
    for row in rows:
        key = row["config_key"]
        val = row["config_value"]
        try:
            config[key] = float(val) if "." in val else int(val)
        except ValueError:
            config[key] = val
    return config


def fetch_rule_config_full(conn):
    """Load tunable rule thresholds with descriptions for the admin UI."""
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT config_key, config_value, description FROM rule_config")
    rows = cur.fetchall()
    cur.close()
    return rows


def update_rule_config(conn, updates_dict):
    """Update rule config values based on a dictionary of keys and new values."""
    cur = conn.cursor()
    for key, value in updates_dict.items():
        cur.execute("UPDATE rule_config SET config_value = %s WHERE config_key = %s", (str(value), key))
    conn.commit()
    cur.close()


# Sensible fallback if the rule_config table hasn't been seeded yet.
DEFAULT_RULE_CONFIG = {
    "LARGE_TXN_STDDEV_K": 3,
    "LARGE_TXN_ABS_FLOOR": 50000,
    "NEW_PAYEE_WINDOW_DAYS": 30,
    "NEW_PAYEE_BURST_COUNT": 3,
    "NEW_PAYEE_BURST_WINDOW_HOURS": 72,
    "ODD_HOURS_BUFFER": 1,
    "PATTERN_BREAK_CHANNEL_RARITY_PCT": 5,
    "PATTERN_BREAK_MIN_RATIO": 1.5,
}
