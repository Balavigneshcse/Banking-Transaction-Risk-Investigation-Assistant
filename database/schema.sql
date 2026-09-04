-- Transaction Risk Investigation Assistant
-- MySQL schema

CREATE DATABASE IF NOT EXISTS txn_risk_assistant
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE txn_risk_assistant;

-- ---------------------------------------------------------------
-- Core entities
-- ---------------------------------------------------------------

CREATE TABLE customers (
  customer_id           INT AUTO_INCREMENT PRIMARY KEY,
  full_name             VARCHAR(120) NOT NULL,
  account_opened_date   DATE NOT NULL,
  created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payees (
  payee_id        INT AUTO_INCREMENT PRIMARY KEY,
  customer_id     INT NOT NULL,
  payee_name      VARCHAR(150) NOT NULL,
  category        VARCHAR(60)  DEFAULT NULL,
  first_seen_date DATE NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
  UNIQUE KEY uniq_customer_payee (customer_id, payee_name)
);

CREATE TABLE transactions (
  txn_id        INT AUTO_INCREMENT PRIMARY KEY,
  customer_id   INT NOT NULL,
  payee_id      INT DEFAULT NULL,
  txn_date      DATE NOT NULL,
  txn_time      TIME NOT NULL,
  amount        DECIMAL(14,2) NOT NULL,
  channel       VARCHAR(40) NOT NULL,
  description   VARCHAR(255) DEFAULT NULL,
  raw_row_ref   VARCHAR(50) DEFAULT NULL,   -- ties back to a row in the originally supplied history file
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
  FOREIGN KEY (payee_id)    REFERENCES payees(payee_id) ON DELETE SET NULL,
  INDEX idx_txn_customer_date (customer_id, txn_date)
);

-- ---------------------------------------------------------------
-- Derived per-customer baseline ("what is normal for this person")
-- ---------------------------------------------------------------

CREATE TABLE customer_baseline (
  customer_id             INT PRIMARY KEY,
  avg_txn_amount          DECIMAL(14,2),
  stddev_txn_amount       DECIMAL(14,2),
  median_txn_amount       DECIMAL(14,2),
  typical_hour_start      TINYINT,   -- 0-23
  typical_hour_end        TINYINT,   -- 0-23
  typical_channels        VARCHAR(255),  -- comma separated list of channels considered normal
  median_monthly_volume   INT,
  computed_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------
-- Investigation reports
-- ---------------------------------------------------------------

CREATE TABLE investigations (
  investigation_id     INT AUTO_INCREMENT PRIMARY KEY,
  customer_id          INT NOT NULL,
  generated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  overall_verdict      ENUM('no_concerns','review_recommended') NOT NULL,
  ai_narrative         TEXT,           -- LLM-written narrative of the findings below (never decides the verdict)
  ai_narrative_source  VARCHAR(10) DEFAULT 'fallback',  -- 'ai' if the LLM call succeeded, 'fallback' if templated
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

CREATE TABLE findings (
  finding_id            INT AUTO_INCREMENT PRIMARY KEY,
  investigation_id      INT NOT NULL,
  rule_code             VARCHAR(40) NOT NULL,
  severity              ENUM('low','medium','high') NOT NULL,
  summary_text          TEXT NOT NULL,
  how_it_differs_text   TEXT,
  first_step_text       TEXT,
  feedback              ENUM('useful', 'false_positive') DEFAULT NULL,
  FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id) ON DELETE CASCADE
);

-- Join table: this is what makes every cited transaction traceable to a finding
CREATE TABLE finding_transactions (
  finding_id  INT NOT NULL,
  txn_id      INT NOT NULL,
  PRIMARY KEY (finding_id, txn_id),
  FOREIGN KEY (finding_id) REFERENCES findings(finding_id) ON DELETE CASCADE,
  FOREIGN KEY (txn_id)     REFERENCES transactions(txn_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------
-- Tunable rule thresholds (kept out of code so the fraud desk can tune sensitivity)
-- ---------------------------------------------------------------

CREATE TABLE rule_config (
  config_key    VARCHAR(60) PRIMARY KEY,
  config_value  VARCHAR(60) NOT NULL,
  description   VARCHAR(255)
);

INSERT INTO rule_config (config_key, config_value, description) VALUES
  ('LARGE_TXN_STDDEV_K',              '3',   'Flag a transaction as unusually large if it exceeds mean + K*stddev of the customer''s own history'),
  ('LARGE_TXN_ABS_FLOOR',             '50000','Absolute rupee floor above which a transaction is always considered for the large-transaction rule'),
  ('NEW_PAYEE_WINDOW_DAYS',           '30',  'A payee is considered "newly added" if first seen within this many days of the most recent transaction'),
  ('NEW_PAYEE_BURST_COUNT',           '3',   'Minimum number of payments to a newly added payee within the burst window to trigger the rule'),
  ('NEW_PAYEE_BURST_WINDOW_HOURS',    '72',  'Time window (hours) within which the burst count is evaluated'),
  ('ODD_HOURS_BUFFER',                '1',   'Hours of buffer added around the customer''s typical active window before flagging as odd-hours'),
  ('PATTERN_BREAK_CHANNEL_RARITY_PCT','5',   'A channel used in fewer than this percent of a customer''s historical transactions is considered rare for them'),
  ('PATTERN_BREAK_MIN_RATIO',         '1.5', 'A rare-channel transaction must be at least this many times the customer''s median amount to trigger the pattern-break rule');

-- ---------------------------------------------------------------
-- Users and Authentication
-- ---------------------------------------------------------------

CREATE TABLE users (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  username        VARCHAR(50) NOT NULL UNIQUE,
  password_hash   VARCHAR(255) NOT NULL,
  role            VARCHAR(20) DEFAULT 'investigator',
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
