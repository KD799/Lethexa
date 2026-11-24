import json
from dataclasses import asdict

from scanner.scan import scan_database


def test_findings_contain_no_raw_values(db):
    raw = set()
    for table in db.get_schema().tables:
        for row in db.sample_rows(table.name, limit=50).rows:
            raw.update(str(v) for v in row if len(str(v)) > 6)
    output = json.dumps([asdict(f) for f in scan_database(db)])
    leaked = [v for v in raw if v in output]
    assert not leaked, "Raw values found in scanner output"