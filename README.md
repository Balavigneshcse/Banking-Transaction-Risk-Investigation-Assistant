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
2. Set up your environment variables:
   Create a `.env` file in the root directory of the project (you can copy the provided `.env.example` file) and add your Gemini API Key and MySQL password:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   DB_PASSWORD=your_mysql_password_here
   ```
   *(Note: The system requires your Gemini API key to generate the AI narrative. Replace with your actual key.)*

3. Start the application:
   ```bash
   python app.py
   ```
4. Open your browser and navigate to: http://localhost:8080

## Environment Variables
* `GEMINI_API_KEY`: Required. The API key for Google's Gemini models used for generating the narrative reports.
* `DB_PASSWORD`: Required. The password for the MySQL database.

## Data Generation
All customer history, transaction sets, and rule-based triggering anomalies were synthesized programmatically using a custom data pipeline to accurately represent standard banking distributions (e.g., typical median spend vs isolated 4+ sigma deviations). The database is pre-seeded with this mock data.

## Demo Video
https://youtu.be/Wp-hEftRCao
