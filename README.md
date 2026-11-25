## Connectors and scanner (setup and run)

Run everything from the repo root (the folder that contains `connectors/`, `scanner/` and `detectors/`).

### 1. Python environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-connectors.txt
```

### 2. Test database
Install PostgreSQL 16 (port 5432), then:
```powershell
Copy-Item .env.example .env      # then edit .env: set the admin password you chose at install
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE lethexa_source;"
psql -U postgres -h 127.0.0.1 -d lethexa_source -f data/synthetic.sql
python -m connectors.setup_readonly
```
`.env` holds passwords and must never be committed. `docker-compose.yml` is an alternative to a native install, but it has not been tested yet.

### 3. Run
```powershell
python -m connectors.smoke     # connection check, schema, 3 sample rows
python -m scanner.scan         # scans all columns, prints the data map, writes data_map.json
python -m pytest               # all tests (DB tests skip if the database is not running)
```
Expected on the synthetic data: 10 tables, 62 columns scanned, 11 PII columns flagged.

### How it works
- `connectors/` is a read-only PostgreSQL connector (test connection, schema and foreign keys, sample rows). The database role is SELECT-only and the session is read-only.
- `scanner/` samples each table, runs `detectors.column_classifier.classify_column` on each column, and keeps only the findings (table, column, category, confidence, reason). Raw values are never stored or logged.

### Known limits
- Only the `public` schema. Samples are the first N rows, not random. Row counts come from Postgres statistics (run `ANALYZE` if they show zero).
- The S3 connector is not built yet (stretch).
- S3 supports CSV, JSON and JSONL files only (no free text). Read-only cannot be proven from the client, so use an IAM user with `s3:ListBucket` and `s3:GetObject` only. S3 has been tested against a mock S3, not real AWS.
- `python -m scanner.locate <identifier>` finds which flagged columns hold one person's data (Postgres only).