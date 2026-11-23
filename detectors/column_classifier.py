"""
Lethexa PII detection (Step 2: column-level classification).

Takes a column name plus a sample of its values and decides whether the column
holds PII. Built on top of rules.detect().

How the confidence is worked out for each category:
    ratio      = (values matching the category) / (non-empty values checked)
    confidence = (average rule confidence of the matching values) * ratio
    +0.05 if the column NAME also hints at the category (e.g. "email_id")

Privacy: values are looked at in memory and thrown away. A ColumnFinding holds
only counts and a reason, never any value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from detectors.rules import detect

DEFAULT_MIN_RATIO = 0.3     # at least 30% of values must match to report a finding
DEFAULT_MAX_SAMPLE = 1000   # never look at more than this many non-empty values
NAME_BOOST = 0.05

# Single-word hints. Column names are split into words first, so "company"
# does NOT trigger the "pan" hint, but "pan_number" does.
_NAME_HINTS = {
    "EMAIL": {"email", "mail"},
    "PHONE": {"phone", "mobile", "tel", "whatsapp"},
    "PAN": {"pan"},
    "AADHAAR": {"aadhaar", "aadhar", "uid"},
    "CREDIT_CARD": {"card", "credit"},
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


def classify_column(
    column_name: str,
    values: Iterable[object],
    *,
    min_ratio: float = DEFAULT_MIN_RATIO,
    max_sample: int = DEFAULT_MAX_SAMPLE,
) -> list[ColumnFinding]:
    """Return findings for one column, most confident first ([] if no PII found)."""
    checked = 0
    match_counts: dict[str, int] = {}
    confidence_sums: dict[str, float] = {}

    for value in values:
        if _is_empty(value):
            continue
        checked += 1
        for match in detect(value):
            match_counts[match.category] = match_counts.get(match.category, 0) + 1
            confidence_sums[match.category] = confidence_sums.get(match.category, 0.0) + match.confidence
        if checked >= max_sample:
            break

    if checked == 0:
        return []

    words = _name_words(column_name)
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

    return sorted(findings, key=lambda f: (-f.confidence, f.category))