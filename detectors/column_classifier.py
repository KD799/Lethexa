"""
Lethexa PII detection (Step 2: column-level classification).

Takes a column name plus a sample of its values and decides whether the column
holds PII. Built on top of rules.detect().

How the confidence is worked out for each category:
    ratio      = (values matching the category) / (non-empty values checked)
    confidence = (average rule confidence of the matching values) * ratio
    +0.05 if the column NAME also hints at the category (e.g. "email_id")

DATE_OF_BIRTH is the exception: a date alone says nothing, so it needs BOTH a
column name that hints at birth AND values that are plausible birth dates.
Its confidence is DOB_CONFIDENCE * ratio.

Privacy: values are looked at in memory and thrown away. A ColumnFinding holds
only counts and a reason, never any value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from detectors.rules import detect

DEFAULT_MIN_RATIO = 0.3     # at least 30% of values must match to report a finding
DEFAULT_MAX_SAMPLE = 1000   # never look at more than this many non-empty values
NAME_BOOST = 0.05

DOB_CATEGORY = "DATE_OF_BIRTH"
DOB_CONFIDENCE = 0.85
MAX_AGE_YEARS = 120
_DOB_NAME_WORDS = {"dob", "birth", "birthday", "birthdate", "born"}
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")

# Single-word hints. Column names are split into words first, so "company"
# does NOT trigger the "pan" hint, but "pan_number" does.
_NAME_HINTS = {
    "EMAIL": {"email", "mail"},
    "PHONE": {"phone", "mobile", "tel", "whatsapp"},
    "PAN": {"pan"},
    "AADHAAR": {"aadhaar", "aadhar", "uid"},
    "CREDIT_CARD": {"card", "credit"},
    "IP_ADDRESS": {"ip"},
}


@dataclass(frozen=True)
class ColumnFinding:
    column: str
    category: str
    confidence: float     # 0.0 to 1.0
    reason: str           # explains the numbers, never contains a value
    sample_size: int      # non-empty values that were checked
    matched_count: int    # how many of them matched this category


def _is_empty(value: object) -> bool:
    return value is None or str(value).strip() == ""


def _name_words(column_name: str) -> set[str]:
    """'customerEmail' -> {'customer', 'email'}; 'pan_number' -> {'pan', 'number'}."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", column_name)
    return {w for w in re.split(r"[^a-z0-9]+", spaced.lower()) if w}


def _as_date(value: object) -> date | None:
    """Turn a date, datetime or common date string into a date (None if it is not one)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _is_plausible_birth_date(value: object, today: date) -> bool:
    parsed = _as_date(value)
    if parsed is None:
        return False
    return date(today.year - MAX_AGE_YEARS, 1, 1) <= parsed <= today


def classify_column(
    column_name: str,
    values: Iterable[object],
    *,
    min_ratio: float = DEFAULT_MIN_RATIO,
    max_sample: int = DEFAULT_MAX_SAMPLE,
) -> list[ColumnFinding]:
    """Return findings for one column, most confident first ([] if no PII found)."""
    words = _name_words(column_name)
    dob_hint = bool(words & _DOB_NAME_WORDS)
    today = date.today()

    checked = 0
    dob_count = 0
    match_counts: dict[str, int] = {}
    confidence_sums: dict[str, float] = {}

    for value in values:
        if _is_empty(value):
            continue
        checked += 1
        for match in detect(value):
            match_counts[match.category] = match_counts.get(match.category, 0) + 1
            confidence_sums[match.category] = confidence_sums.get(match.category, 0.0) + match.confidence
        if dob_hint and _is_plausible_birth_date(value, today):
            dob_count += 1
        if checked >= max_sample:
            break

    if checked == 0:
        return []

    findings: list[ColumnFinding] = []

    for category, count in match_counts.items():
        ratio = count / checked
        if ratio < min_ratio:
            continue

        average = confidence_sums[category] / count
        confidence = average * ratio
        reason = f"{count} of {checked} sampled values match {category} rules (average rule confidence {average:.2f})"

        if words & _NAME_HINTS.get(category, set()):
            confidence = min(1.0, confidence + NAME_BOOST)
            reason += f"; column name also suggests {category}"

        findings.append(
            ColumnFinding(
                column=column_name,
                category=category,
                confidence=round(confidence, 2),
                reason=reason,
                sample_size=checked,
                matched_count=count,
            )
        )

    if dob_hint and dob_count and dob_count / checked >= min_ratio:
        findings.append(
            ColumnFinding(
                column=column_name,
                category=DOB_CATEGORY,
                confidence=round(DOB_CONFIDENCE * dob_count / checked, 2),
                reason=(
                    f"{dob_count} of {checked} sampled values are dates in a plausible "
                    f"birth-date range; column name suggests date of birth"
                ),
                sample_size=checked,
                matched_count=dob_count,
            )
        )

    return sorted(findings, key=lambda f: (-f.confidence, f.category))