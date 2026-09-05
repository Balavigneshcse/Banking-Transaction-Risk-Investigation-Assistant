# Architecture & Design: Transaction Risk Investigation Assistant

## Overview

The **Transaction Risk Investigation Assistant** is a decision-support tool for bank fraud investigators. It automates the routine, time-consuming parts of reviewing a customer's transaction history, while leaving the final judgment strictly to the human investigator.

## Core Philosophy

1. **Deterministic Detection**: The system uses hard-coded, auditable rules (e.g., "Transaction > 3 standard deviations above mean") rather than a black-box machine learning model for detection. This ensures every finding can be explained mathematically and traced back to specific rows of data.
2. **AI as a Communicator, Not a Decider**: The AI (LLM) is used exclusively to translate structured rule hits into a readable narrative and to answer Q&A based *only* on that structured data. It is explicitly forbidden from making decisions about fraud.
3. **Graceful Degradation**: If the AI API is unavailable or unconfigured, the system falls back to a template-based deterministic narrative, ensuring investigators are never blocked.
4. **Baseline vs. Global Thresholds**: The system profiles what is "normal" for each specific customer (their baseline) rather than applying a one-size-fits-all threshold across the whole bank.

---

## Component Architecture

### 1. Data Layer (`database/schema.sql`)
- **Customers & Payees**: Basic relationship mapping.
- **Transactions**: Raw transaction history.
- **Customer Baseline**: Pre-computed statistics per customer (average spend, standard deviation, median, typical active hours, common channels).
- **Rule Config**: Tunable parameters for the rule engine (e.g., `LARGE_TXN_STDDEV_K`, `NEW_PAYEE_WINDOW_DAYS`). These can be adjusted by admins via the UI without touching code.
- **Investigations & Findings**: Audit trail of every report generated. Findings link to specific `txn_id`s for traceability, and include an investigator feedback mechanism (Useful / False Positive) to build datasets for future ML models.

### 2. Analytical Engine (`backend/`)
- **`baseline.py`**: Computes the `customer_baseline` statistics.
- **`rules.py`**: Contains the deterministic risk rules:
  - `LARGE_TXN`: Checks if a transaction is mathematically unusual for the specific customer.
  - `NEW_PAYEE_BURST`: Detects rapid, clustered payments to a newly added payee.
  - `ODD_HOURS`: Checks if activity falls outside the customer's typical time window.
  - `PATTERN_BREAK`: Flags usage of a channel that is statistically rare for this customer, if the amount is also large.
- **`aggregator.py`**: Orchestrates the process—runs the baseline, runs the rules, synthesizes the findings, and assigns an `overall_verdict` (`no_concerns` or `review_recommended`).

### 3. AI Narrative Layer (`backend/ai_narrative.py`)
- Takes the JSON output of the aggregator.
- Injects it into a strict prompt.
- **Anthropic Claude** processes the data to generate a short, professional summary.
- The prompt includes strict negative constraints: *Never invent data, never conclude fraud.*

### 4. Presentation Layer (`frontend/`)
- **Vanilla JS & CSS**: A lightweight, fast, modern dashboard.
- **Chart.js**: Visualizes transaction patterns (e.g., Scatter plot showing routine vs. flagged transactions over time) to provide immediate visual context.
- **Micro-animations**: Staggered rendering, loading skeletons, and hover states to create a premium, responsive feel.
- **Print/Export**: Specialized CSS media queries format the dashboard cleanly for PDF generation, hiding interactive elements and optimizing for A4 reading.

---

## The Investigator Workflow

1. **Select Customer**: Investigator selects a customer from the queue.
2. **Review Baseline**: Investigator sees at a glance what is "normal" for this person (Chart & Stats).
3. **Run Investigation**: The rule engine evaluates the history against the baseline.
4. **Read Narrative**: A clear, concise summary explains *why* the rules fired, or confirms routine activity.
5. **Inspect Traces**: Clicking any cited transaction jumps directly to the raw data row.
6. **Provide Feedback**: Investigator clicks "Yes (Useful)" or "False Positive" on findings, closing the loop.
7. **Export**: The report can be exported to PDF for attachment to a SAR (Suspicious Activity Report).
