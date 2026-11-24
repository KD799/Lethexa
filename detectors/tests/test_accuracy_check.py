"""
Tests for detectors/accuracy_check.py

Run from the repo root:
    python -m unittest discover -s detectors/tests -t . -v
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from data.generate_synthetic import Column, Table, build_dataset
from detectors.accuracy_check import (
    Counts,
    build_report,
    evaluate,
    main,
    value_level,
)


class CountsTests(unittest.TestCase):
    def test_precision_and_recall(self):
        counts = Counts(tp=8, fp=2, fn=2)
        self.assertAlmostEqual(counts.precision, 0.8)
        self.assertAlmostEqual(counts.recall, 0.8)

    def test_no_data_gives_none(self):
        self.assertIsNone(Counts().precision)
        self.assertIsNone(Counts().recall)


class SmallHandBuiltTables(unittest.TestCase):
    """Tiny tables where we know the right answer in advance."""

    def test_missed_column_is_counted_as_false_negative(self):
        table = Table("t", [Column("email", "TEXT", "EMAIL")], rows=[("hello",)] * 5)
        result = evaluate([table])
        self.assertEqual(result.per_category["EMAIL"].fn, 1)
        self.assertEqual(len(result.misses), 1)

    def test_clean_column_flagged_is_a_false_positive(self):
        rows = [(f"a{i}@example.com",) for i in range(5)]
        table = Table("t", [Column("notes", "TEXT", "NONE")], rows=rows)
        result = evaluate([table])
        self.assertEqual(result.per_category["EMAIL"].fp, 1)
        self.assertEqual(len(result.false_positives), 1)

    def test_wrong_category_is_both_a_miss_and_a_false_positive(self):
        rows = [(f"a{i}@example.com",) for i in range(5)]
        table = Table("t", [Column("contact", "TEXT", "PHONE")], rows=rows)
        result = evaluate([table])
        self.assertEqual(result.per_category["EMAIL"].fp, 1)
        self.assertEqual(result.per_category["PHONE"].fn, 1)

    def test_pii_without_a_detector_is_listed_as_not_covered(self):
        table = Table("t", [Column("full_name", "TEXT", "NAME")], rows=[("Priya Sharma",)] * 5)
        result = evaluate([table])
        self.assertEqual(result.uncovered, ["t.full_name (NAME)"])
        self.assertEqual(result.total.fn, 0)        # not counted as a detector miss


class SyntheticDatasetResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = build_dataset()
        cls.result = evaluate(cls.tables)

    def test_every_detectable_column_is_found_with_no_wrong_flags(self):
        self.assertEqual(self.result.total.tp, 13)
        self.assertEqual(self.result.total.fp, 0)
        self.assertEqual(self.result.total.fn, 0)

    def test_per_category_column_counts(self):
        expected = {"EMAIL": 3, "PHONE": 4, "PAN": 2, "AADHAAR": 1, "CREDIT_CARD": 1}
        for category, count in expected.items():
            with self.subTest(category=category):
                self.assertEqual(self.result.per_category[category].tp, count)

    def test_uncovered_and_coverage(self):
        self.assertEqual(len(self.result.uncovered), 3)
        self.assertAlmostEqual(self.result.coverage, 13 / 16)

    def test_very_low_threshold_creates_false_positives_on_lookalike_columns(self):
        loose = evaluate(self.tables, min_ratio=0.05)
        self.assertGreater(len(loose.false_positives), 0)
        text = " ".join(loose.false_positives)
        self.assertTrue("payment_ref" in text or "tracking_number" in text)

    def test_value_level_numbers(self):
     found, flagged_clean = value_level(self.tables)
     for category, (detected, checked) in found.items():
        if category == "DATE_OF_BIRTH":
            continue  # needs the column name, so it has no value-level rule
        with self.subTest(category=category):
            self.assertGreater(checked, 0)
            self.assertEqual(detected, checked)


class ReportTests(unittest.TestCase):
    def test_report_has_all_sections(self):
        report = build_report()
        for heading in ["## Result against the PRD targets", "## Per category",
                        "## Not covered yet", "## Mistakes", "## Look-alike columns",
                        "## Threshold sensitivity"]:
            with self.subTest(heading=heading):
                self.assertIn(heading, report)
        self.assertIn("PASS", report)

    def test_report_never_contains_example_values(self):
        report = build_report()
        self.assertNotIn("@example", report)

    def test_main_prints_and_writes_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "sub" / "report.md"
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                main(["--write", str(target)])
            self.assertTrue(target.exists())
            self.assertIn("Lethexa detector accuracy report", target.read_text(encoding="utf-8"))
            self.assertIn("Saved to", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
