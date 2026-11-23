"""
Lethexa accuracy check (Step 4).

Runs the column classifier on every column of the synthetic dataset, compares
the results with the answer key (data/labels.json logic), and prints a report
with precision, recall and a list of mistakes.

Run from the repo root:
    python -m detectors.accuracy_check
    python -m detectors.accuracy_check --write docs/accuracy-report.md

Definitions (all at COLUMN level, because the data map is made of columns):
    true positive   column flagged with exactly the right category
    false positive  column flagged with a wrong category, or a clean column flagged
    false negative  column that holds a detectable category but was not flagged
    precision       true positives / (true positives + false positives)
    recall          true positives / (true positives + false negatives)

Columns with PII that no detector exists for yet (names, addresses, dates of
birth, IP addresses) are listed separately as "not covered yet". They are NOT
counted as false negatives, but they DO count against "coverage".
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from data.generate_synthetic import (
    DEFAULT_CUSTOMERS,
    DEFAULT_SEED,
    DETECTABLE,
    OTHER_PII,
    Table,
    build_dataset,
    labels_for,
)
from detectors.column_classifier import DEFAULT_MIN_RATIO, classify_column
from detectors.rules import detect

TARGET_PRECISION = 0.90     # from the PRD
TARGET_RECALL = 0.80        # from the PRD
SWEEP_RATIOS = [0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 0.90]


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else None


@dataclass
class Evaluation:
    min_ratio: float
    per_category: dict[str, Counts]
    false_positives: list[str]
    misses: list[str]
    uncovered: list[str]

    @property
    def total(self) -> Counts:
        counts = Counts()
        for c in self.per_category.values():
            counts.tp += c.tp
            counts.fp += c.fp
            counts.fn += c.fn
        return counts

    @property
    def coverage(self) -> float | None:
        """Share of ALL PII columns (including ones we have no detector for) that were found."""
        denominator = self.total.tp + self.total.fn + len(self.uncovered)
        return self.total.tp / denominator if denominator else None


def _is_empty(value: object) -> bool:
    return value is None or str(value).strip() == ""


def _column_values(table: Table, index: int) -> list[object]:
    return [row[index] for row in table.rows]


def evaluate(tables: list[Table], min_ratio: float = DEFAULT_MIN_RATIO) -> Evaluation:
    labels = labels_for(tables)
    per_category = {category: Counts() for category in DETECTABLE}
    false_positives: list[str] = []
    misses: list[str] = []
    uncovered: list[str] = []

    for table in tables:
        for index, column in enumerate(table.columns):
            key = f"{table.name}.{column.name}"
            label = labels[key]
            findings = classify_column(column.name, _column_values(table, index), min_ratio=min_ratio)
            predicted = {f.category for f in findings}

            for category in sorted(predicted):
                if category == label:
                    per_category[category].tp += 1
                else:
                    per_category[category].fp += 1
                    false_positives.append(f"{key} (really {label}) was flagged as {category}")

            if label in DETECTABLE and label not in predicted:
                per_category[label].fn += 1
                misses.append(f"{key} should be {label} but was not found")

            if label in OTHER_PII:
                uncovered.append(f"{key} ({label})")

    return Evaluation(min_ratio, per_category, false_positives, misses, uncovered)


def value_level(tables: list[Table]):
    """Look at individual values.

    Returns (found, flagged_clean):
      found[category]  = [values detected, values checked] in columns that really hold that category
      flagged_clean    = [(column, values flagged, values checked)] for clean columns where some values look like PII
    """
    labels = labels_for(tables)
    found = {category: [0, 0] for category in DETECTABLE}
    flagged_clean: list[tuple[str, int, int]] = []

    for table in tables:
        for index, column in enumerate(table.columns):
            key = f"{table.name}.{column.name}"
            label = labels[key]
            values = [x for x in _column_values(table, index) if not _is_empty(x)]
            if label in DETECTABLE:
                hits = sum(1 for x in values if label in {m.category for m in detect(x)})
                found[label][0] += hits
                found[label][1] += len(values)
            elif label == "NONE":
                flagged = sum(1 for x in values if detect(x))
                if flagged:
                    flagged_clean.append((key, flagged, len(values)))

    return found, flagged_clean


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _status(value: float | None, target: float) -> str:
    if value is None:
        return "n/a"
    return "PASS" if value >= target else "FAIL"


def build_report(seed: int = DEFAULT_SEED, n_customers: int = DEFAULT_CUSTOMERS,
                 min_ratio: float = DEFAULT_MIN_RATIO) -> str:
    tables = build_dataset(seed, n_customers)
    result = evaluate(tables, min_ratio)
    found, flagged_clean = value_level(tables)
    total = result.total

    n_columns = sum(len(t.columns) for t in tables)
    n_pii = total.tp + total.fn + len(result.uncovered)

    lines = [
        "# Lethexa detector accuracy report",
        "",
        f"Dataset: seed {seed}, {n_customers} customers, {len(tables)} tables, {n_columns} columns "
        f"({n_pii} hold PII). Column threshold: {min_ratio:.0%} of values must match.",
        "",
        "## Result against the PRD targets",
        "",
        "| Measure | Result | Target | Status |",
        "|---|---|---|---|",
        f"| Column precision | {_pct(total.precision)} | at least {TARGET_PRECISION:.0%} | {_status(total.precision, TARGET_PRECISION)} |",
        f"| Column recall (rule-based categories) | {_pct(total.recall)} | at least {TARGET_RECALL:.0%} | {_status(total.recall, TARGET_RECALL)} |",
        f"| Coverage of all PII columns | {_pct(result.coverage)} | none set | info |",
        "",
        "## Per category",
        "",
        "| Category | Found | Missed | Wrong | Precision | Recall | Values detected |",
        "|---|---|---|---|---|---|---|",
    ]
    for category in DETECTABLE:
        c = result.per_category[category]
        detected, checked = found[category]
        value_share = _pct(detected / checked) if checked else "n/a"
        lines.append(
            f"| {category} | {c.tp} | {c.fn} | {c.fp} | {_pct(c.precision)} | {_pct(c.recall)} | {value_share} |"
        )

    lines += ["", "## Not covered yet (needs the NLP classifier)", ""]
    lines += [f"- {item}" for item in result.uncovered] or ["- none"]

    lines += ["", "## Mistakes", ""]
    lines += [f"- False positive: {item}" for item in result.false_positives]
    lines += [f"- Missed: {item}" for item in result.misses]
    if not result.false_positives and not result.misses:
        lines.append("- none")

    lines += [
        "",
        "## Look-alike columns",
        "",
        "Clean columns where some single values happen to look like PII "
        "(random digits can pass a checksum by chance). The column threshold stops these from being flagged.",
        "",
    ]
    if flagged_clean:
        lines += ["| Column | Values flagged | Checked | Share |", "|---|---|---|---|"]
        for key, flagged, checked in flagged_clean:
            lines.append(f"| {key} | {flagged} | {checked} | {_pct(flagged / checked)} |")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Threshold sensitivity",
        "",
        "What happens if we change how much of a column must match before we flag it.",
        "",
        "| Threshold | Precision | Recall | Wrong flags | Missed |",
        "|---|---|---|---|---|",
    ]
    for ratio in SWEEP_RATIOS:
        e = evaluate(tables, ratio)
        marker = " (current)" if abs(ratio - min_ratio) < 1e-9 else ""
        lines.append(
            f"| {ratio:.0%}{marker} | {_pct(e.total.precision)} | {_pct(e.total.recall)} "
            f"| {len(e.false_positives)} | {len(e.misses)} |"
        )

    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Measure detector accuracy on the synthetic dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--customers", type=int, default=DEFAULT_CUSTOMERS)
    parser.add_argument("--min-ratio", type=float, default=DEFAULT_MIN_RATIO)
    parser.add_argument("--write", type=Path, help="also save the report to this file, e.g. docs/accuracy-report.md")
    args = parser.parse_args(argv)

    report = build_report(args.seed, args.customers, args.min_ratio)
    print(report)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(report, encoding="utf-8")
        print(f"Saved to {args.write}")


if __name__ == "__main__":
    main()
