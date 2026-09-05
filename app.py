"""
Flask API for the Transaction Risk Investigation Assistant.

Endpoints:
  GET  /api/customers                         -> list customers
  GET  /api/customers/<id>/transactions        -> raw transaction history (for the table view)
  POST /api/customers/<id>/investigate         -> run the rule engine fresh, persist, return report
  GET  /api/customers/<id>/investigations      -> list past investigations for this customer

Also serves the static frontend from ./frontend.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory

from src.db import get_connection, fetch_rule_config, fetch_rule_config_full, update_rule_config, DEFAULT_RULE_CONFIG
from src.aggregator import run_investigation
from src.ai_narrative import answer_question

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def get_config(conn):
    try:
        cfg = fetch_rule_config(conn)
        return cfg if cfg else DEFAULT_RULE_CONFIG
    except Exception:
        return DEFAULT_RULE_CONFIG


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/config", methods=["GET"])
def get_rule_config():
    conn = get_connection()
    try:
        cfg = fetch_rule_config_full(conn)
        return jsonify(cfg)
    finally:
        conn.close()


@app.route("/api/config", methods=["POST"])
def update_rule_config_endpoint():
    updates = request.get_json(force=True)
    if not updates:
        return jsonify({"error": "No updates provided"}), 400
    
    conn = get_connection()
    try:
        update_rule_config(conn, updates)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/findings/<int:finding_id>/feedback", methods=["POST"])
def submit_feedback(finding_id):
    body = request.get_json(force=True)
    feedback = body.get("feedback")
    if feedback not in ("useful", "false_positive"):
        return jsonify({"error": "Invalid feedback value"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE findings SET feedback = %s WHERE finding_id = %s", (feedback, finding_id))
        conn.commit()
        cur.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/health", methods=["GET"])
def health():
    """Simple health check — confirms the backend is running and can reach MySQL."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": str(e)}), 503


@app.route("/api/customers", methods=["GET"])
def list_customers():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT customer_id, full_name, account_opened_date FROM customers ORDER BY full_name")
    rows = cur.fetchall()
    for r in rows:
        r["account_opened_date"] = str(r["account_opened_date"])
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/customers/<int:customer_id>/transactions", methods=["GET"])
def get_transactions(customer_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT t.txn_id, t.txn_date, t.txn_time, t.amount, t.channel, t.description,
               p.payee_name
        FROM transactions t
        LEFT JOIN payees p ON t.payee_id = p.payee_id
        WHERE t.customer_id = %s
        ORDER BY t.txn_date, t.txn_time
        """,
        (customer_id,),
    )
    rows = cur.fetchall()
    for r in rows:
        r["txn_date"] = str(r["txn_date"])
        r["txn_time"] = str(r["txn_time"])
        r["amount"] = float(r["amount"])
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/customers/<int:customer_id>/investigate", methods=["POST"])
def investigate(customer_id):
    conn = get_connection()
    try:
        config = get_config(conn)
        report = run_investigation(conn, customer_id, config)
        return jsonify(report)
    finally:
        conn.close()


@app.route("/api/customers/<int:customer_id>/investigations", methods=["GET"])
def list_investigations(customer_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """SELECT investigation_id, generated_at, overall_verdict
           FROM investigations WHERE customer_id=%s ORDER BY generated_at DESC""",
        (customer_id,),
    )
    rows = cur.fetchall()
    for r in rows:
        r["generated_at"] = str(r["generated_at"])
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/customers/<int:customer_id>/ask", methods=["POST"])
def ask(customer_id):
    body = request.get_json(force=True) or {}
    report = body.get("report")
    question = body.get("question", "").strip()
    history = body.get("history", [])

    if not report or not question:
        return jsonify({"error": "Both 'report' and 'question' are required."}), 400

    answer, source = answer_question(report, question, history)
    return jsonify({"answer": answer, "source": source})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
