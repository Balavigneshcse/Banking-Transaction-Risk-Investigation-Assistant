"""
AI layer for the investigation assistant using Gemini.
"""

import os
import json
import warnings

# Suppress the deprecation warning for google.generativeai to keep terminal clean
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
import google.generativeai as genai

MODEL_NAME = "gemini-1.5-pro"

SYSTEM_PROMPT = """You are writing for a bank's internal fraud desk. You will be given a
JSON object describing an automated transaction-risk report: an overall verdict, a
customer baseline, and a list of rule-based findings, each with the exact transactions
that triggered it.

Rules you must follow strictly:
- Use ONLY the facts in the JSON. Never invent a transaction, amount, date, or payee
  that isn't present in it.
- NEVER state or imply that fraud has occurred, that the customer did anything wrong,
  or that a transaction is confirmed illegitimate. Use hedged, investigative language
  ("warrants a closer look", "differs from their usual pattern", "worth confirming with
  the customer") - the same way the input findings are already phrased.
- Do not change or contradict the report's own overall_verdict. If it is "no_concerns",
  your narrative must also read as reassuring and closed, not hint at hidden risk.
- Write for a human investigator who is about to decide what to do next: be concise,
  concrete, and reference specific transaction ids so it's traceable back to the report.
- Do not use markdown headers. Two to four short paragraphs, plain prose.
"""

ASK_SYSTEM_PROMPT = """You are a fraud-desk assistant answering an investigator's question
about ONE specific investigation report, provided to you as JSON.

Rules you must follow strictly:
- Answer using ONLY the data in the provided report JSON. If the answer isn't in there,
  say plainly that the report doesn't contain that information - do not guess or invent.
- NEVER state or imply that fraud has occurred or that the customer is guilty of anything.
  You flag, explain, and point to evidence; the investigator judges.
- When you reference a transaction, cite its txn_id, date, and amount so it's traceable.
- Keep answers short and direct - a few sentences unless the question needs a list.
"""

def _get_model(system_instruction):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=system_instruction
        )
    except Exception as e:
        return None

def _fallback_narrative(report):
    if report["overall_verdict"] == "no_concerns":
        return (
            f"This customer's {report['transactions_reviewed']} transactions on file were checked "
            f"against all configured risk rules and none were triggered. Spending sits close to their "
            f"usual pattern (typical transaction around ₹{report['baseline_summary']['avg_amount']:,.2f}, "
            f"active hours {report['baseline_summary']['typical_hours']}, usual channels "
            f"{', '.join(report['baseline_summary']['typical_channels']) or 'n/a'}). "
            f"No investigator action is indicated at this time."
        )
    lines = [
        f"{len(report['findings'])} finding(s) were raised against {report['transactions_reviewed']} "
        f"transactions on file for this customer, based on how their activity compares to their own history."
    ]
    for f in report["findings"]:
        txn_ids = ", ".join(f"#{t['txn_id']}" for t in f["transactions"])
        lines.append(f"{f['summary']} (transactions {txn_ids}). {f['first_step']}")
    return " ".join(lines)

def generate_narrative(report):
    model = _get_model(SYSTEM_PROMPT)
    if model is None:
        return _fallback_narrative(report), "fallback"

    try:
        payload = json.dumps(report, default=str)
        response = model.generate_content(f"Here is the report JSON:\n{payload}")
        text = response.text.strip()
        return (text or _fallback_narrative(report)), ("ai" if text else "fallback")
    except Exception:
        return _fallback_narrative(report), "fallback"

def answer_question(report, question, history=None):
    model = _get_model(ASK_SYSTEM_PROMPT)
    if model is None:
        return (
            "AI Q&A isn't configured in this environment (no GEMINI_API_KEY set). "
            "You can still review the findings and cited transactions above directly.",
            "fallback",
        )

    try:
        payload = json.dumps(report, default=str)
        messages = [{"role": "user", "parts": [f"Report JSON:\n{payload}"]}]
        if history:
            for turn in history:
                role = "model" if turn["role"] == "assistant" else "user"
                messages.append({"role": role, "parts": [turn["content"]]})
        messages.append({"role": "user", "parts": [question]})

        response = model.generate_content(messages)
        text = response.text.strip()
        return (text or "I couldn't generate an answer from the report data."), "ai"
    except Exception as e:
        return f"AI Q&A request failed ({e.__class__.__name__}). Please review the report directly.", "fallback"
