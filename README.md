TRACK_ID=PS6

# Banking Transaction Risk Investigation Assistant

## Overview
A high-performance investigation assistant built for a bank's fraud desk. The system evaluates a customer's transaction history against configurable deterministic risk rules (e.g., standard deviation bursts, off-hours activity, new payee velocity). 

When a transaction triggers a rule, the system generates an audit-ready Suspicious Activity Report (SAR) payload. Instead of a hardcoded string, the system passes the exact data envelope to the Gemini Pro model to synthesize a professional, grounded narrative explanation for the investigator. The LLM is strictly constrained to the provided data and never makes independent judgements about fraud—it simply explains the anomaly clearly to the human investigator.

## Running the Application
The application is a Python-based server that serves both the API endpoints and the built frontend SPA simultaneously.

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set your Gemini API key and Database Password in your terminal (using PowerShell):
   ```powershell
   $env:GEMINI_API_KEY="YOUR_API_KEY_HERE"
   $env:DB_PASSWORD="Bala@sql"
   ```
   *(Note: The system requires your Gemini API key to generate the AI narrative. Replace YOUR_API_KEY_HERE with your actual key.)*

3. Start the application:
   ```bash
   python app.py
   ```
4. Open your browser and navigate to: http://localhost:8000

## Environment Variables
* `GEMINI_API_KEY`: Required. The API key for Google's Gemini models used for generating the narrative reports.
* `DB_PASSWORD`: Required. The password for the MySQL database.

## Data Generation
All customer history, transaction sets, and rule-based triggering anomalies were synthesized programmatically using a custom data pipeline to accurately represent standard banking distributions (e.g., typical median spend vs isolated 4+ sigma deviations). The database is pre-seeded with this mock data.

## Demo Video
[Demo Video Link] - (Link to be added prior to submission)
