import json
from dataclasses import asdict

from scanner.scan import scan_s3


def test_scan_s3_flags_pii_columns_only(s3):
    flagged = {(f.table.rsplit("/", 1)[-1], f.column, f.category) for f in scan_s3(s3)}
    assert ("customers.csv", "email", "EMAIL") in flagged
    assert ("customers.csv", "phone", "PHONE") in flagged
    assert ("events.jsonl", "contact", "EMAIL") in flagged
    assert not any(column == "name" for _, column, _ in flagged)


def test_scan_s3_findings_contain_no_raw_values(s3):
    output = json.dumps([asdict(f) for f in scan_s3(s3)])
    assert "asha@example.com" not in output
    assert "9876543210" not in output