import json
from pathlib import Path

from scanner.scan import scan_database

LABELS = Path(__file__).resolve().parents[2] / "data" / "labels.json"
DETECTED = {"EMAIL", "PHONE", "PAN", "AADHAAR", "CREDIT_CARD"}


def _expected() -> set[tuple[str, str]]:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    return {(col, cat) for col, cat in labels.items() if cat in DETECTED}


def _found(db) -> set[tuple[str, str]]:
    return {(f"{f.table}.{f.column}", f.category) for f in scan_database(db)}


def test_scanner_finds_every_labeled_column(db):
    missed = _expected() - _found(db)
    assert not missed, f"Missed: {sorted(missed)}"


def test_scanner_has_no_false_positives(db):
    extra = _found(db) - _expected()
    assert not extra, f"Wrongly flagged: {sorted(extra)}"