USE txn_risk_assistant;

ALTER TABLE findings ADD COLUMN feedback ENUM('useful', 'false_positive') DEFAULT NULL;
