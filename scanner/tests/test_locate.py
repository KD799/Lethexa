import json
import re
from dataclasses import asdict

import pytest

from scanner.locate import locate_subject
from scanner.scan import scan_database


@pytest.fixture(scope="module")
def findings(db):
    return scan_database(db)


def _first(db, table, column):
    return db.sample_rows(table, limit=1).column_values(column)[0]


def _summary(result):
    return [(m.table, m.column, m.match_count) for m in result.matches]


def test_email_is_found_in_customers(db, findings):
    result = locate_subject(db, findings, _first(db, "customers", "email"))
    assert result.category == "EMAIL"
    assert ("customers", "email") in {(m.table, m.column) for m in result.matches}


def test_email_match_ignores_case(db, findings):
    email = _first(db, "customers", "email")
    lower = locate_subject(db, findings, email.lower(), "EMAIL")
    upper = locate_subject(db, findings, email.upper(), "EMAIL")
    assert _summary(lower) == _summary(upper) and lower.total_rows >= 1


def test_phone_match_ignores_format(db, findings):
    digits = re.sub(r"\D", "", str(_first(db, "customers", "mobile")))[-10:]
    plain = locate_subject(db, findings, digits, "PHONE")
    formatted = locate_subject(db, findings, f"+91 {digits}", "PHONE")
    assert _summary(plain) == _summary(formatted) and plain.total_rows >= 1


def test_unknown_identifier_matches_nothing(db, findings):
    result = locate_subject(db, findings, "nobody-here@example.invalid")
    assert result.matches == [] and result.total_rows == 0


def test_injection_style_identifier_is_harmless(db, findings):
    result = locate_subject(db, findings, "x'; DROP TABLE customers;--", "EMAIL")
    assert result.total_rows == 0
    assert "customers" in {t.name for t in db.get_schema().tables}


def test_result_contains_no_identifier(db, findings):
    email = _first(db, "customers", "email")
    output = json.dumps(asdict(locate_subject(db, findings, email)), default=str)
    assert str(email) not in output


def test_unsupported_or_unrecognised_identifier_rejected(db, findings):
    with pytest.raises(ValueError):
        locate_subject(db, findings, "1990-01-01", "DATE_OF_BIRTH")
    with pytest.raises(ValueError):
        locate_subject(db, findings, "just some words")