"""Find which flagged columns hold one person's identifier.

Only columns the scanner flagged with the identifier's category are searched.
Results hold table, column, counts and row keys. The identifier itself is
never stored, logged or echoed in an error.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from connectors import PostgresConnector, RowMatches
from detectors.rules import detect

from .scan import Finding, scan_database

SEARCHABLE = ("EMAIL", "PHONE", "PAN", "AADHAAR", "CREDIT_CARD", "IP_ADDRESS")


@dataclass(frozen=True)
class LocateResult:
    category: str
    columns_searched: int
    matches: list[RowMatches]

    @property
    def total_rows(self) -> int:
        return sum(m.match_count for m in self.matches)


def _infer_category(identifier: str) -> str:
    candidates = [m.category for m in detect(identifier) if m.category in SEARCHABLE]
    if not candidates:
        raise ValueError("Could not tell what kind of identifier this is; pass category=...")
    return candidates[0]


def _prepare(category: str, identifier: str) -> tuple[str, str]:
    """Return (match mode, normalised value) so formats like +91 or spaces still match."""
    text = str(identifier).strip()
    if not text:
        raise ValueError("Identifier is empty")
    if category == "EMAIL":
        return "lower", text.lower()
    if category == "PAN":
        return "upper", text.upper()
    if category == "PHONE":
        digits = re.sub(r"\D", "", text)
        if len(digits) < 10:
            raise ValueError("Identifier is not a valid phone number")
        return "phone10", digits[-10:]
    if category in ("AADHAAR", "CREDIT_CARD"):
        digits = re.sub(r"\D", "", text)
        if not digits:
            raise ValueError("Identifier has no digits")
        return "digits", digits
    return "exact", text  # IP_ADDRESS


def locate_subject(
    db: PostgresConnector,
    findings: list[Finding],
    identifier: str,
    category: str | None = None,
    *,
    max_keys: int = 20,
) -> LocateResult:
    category = category or _infer_category(identifier)
    if category not in SEARCHABLE:
        raise ValueError(f"Cannot look people up by {category}")
    mode, value = _prepare(category, identifier)

    # Postgres columns only; S3 findings (table starts with s3://) are not searched here.
    targets = sorted({
        (f.table, f.column) for f in findings
        if f.category == category and not f.table.startswith("s3://")
    })
    matches = []
    for table, column in targets:
        found = db.find_rows(table, column, value, mode=mode, limit=max_keys)
        if found.match_count:
            matches.append(found)
    return LocateResult(category, len(targets), matches)


def main() -> None:
    from connectors import PostgresConfig

    args = sys.argv[1:]
    if not args:
        print("Usage: python -m scanner.locate <identifier> [CATEGORY]")
        return
    category = args[1].upper() if len(args) > 1 else None
    with PostgresConnector(PostgresConfig.from_env()) as db:
        result = locate_subject(db, scan_database(db), args[0], category)
    print(f"{result.category}: searched {result.columns_searched} flagged columns, "
          f"{result.total_rows} matching rows")
    for m in result.matches:
        print(f"  {m.table}.{m.column}: {m.match_count} rows, keys {list(m.keys)}")


if __name__ == "__main__":
    main()