# Lethexa detector accuracy report

Dataset: seed 2026, 200 customers, 10 tables, 62 columns (16 hold PII). Column threshold: 30% of values must match.

## Result against the PRD targets

| Measure | Result | Target | Status |
|---|---|---|---|
| Column precision | 100.0% | at least 90% | PASS |
| Column recall (rule-based categories) | 100.0% | at least 80% | PASS |
| Coverage of all PII columns | 68.8% | none set | info |

## Per category

| Category | Found | Missed | Wrong | Precision | Recall | Values detected |
|---|---|---|---|---|---|---|
| EMAIL | 3 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| PHONE | 4 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| PAN | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| AADHAAR | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| CREDIT_CARD | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% |

## Not covered yet (needs the NLP classifier)

- customers.full_name (NAME)
- customers.date_of_birth (DATE_OF_BIRTH)
- addresses.address_line (ADDRESS)
- employees.full_name (NAME)
- app_logs.ip_address (IP_ADDRESS)

## Mistakes

- none

## Look-alike columns

Clean columns where some single values happen to look like PII (random digits can pass a checksum by chance). The column threshold stops these from being flagged.

| Column | Values flagged | Checked | Share |
|---|---|---|---|
| payments.payment_ref | 31 | 301 | 10.3% |
| delivery_logs.tracking_number | 27 | 301 | 9.0% |

## Threshold sensitivity

What happens if we change how much of a column must match before we flag it.

| Threshold | Precision | Recall | Wrong flags | Missed |
|---|---|---|---|---|
| 5% | 84.6% | 100.0% | 2 | 0 |
| 10% | 91.7% | 100.0% | 1 | 0 |
| 20% | 100.0% | 100.0% | 0 | 0 |
| 30% (current) | 100.0% | 100.0% | 0 | 0 |
| 50% | 100.0% | 100.0% | 0 | 0 |
| 70% | 100.0% | 100.0% | 0 | 0 |
| 90% | 100.0% | 100.0% | 0 | 0 |
