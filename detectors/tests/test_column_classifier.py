"""
Tests for detectors/column_classifier.py

Run from the repo root:
    python -m unittest discover -s detectors/tests -t . -v

All sample values are fake.
"""

import unittest

from detectors.column_classifier import classify_column
from detectors.rules import verhoeff_check_digit


def emails(n):
    return [f"user{i}@example.com" for i in range(n)]


def phones(n):
    return [str(9000000000 + i) for i in range(n)]


def aadhaars(n):
    result = []
    for i in range(n):
        payload = f"2341234{i:04d}"          # 11 digits, starts with 2
        result.append(payload + verhoeff_check_digit(payload))
    return result


def categories(findings):
    return [f.category for f in findings]


class ColumnClassifierTests(unittest.TestCase):
    def test_column_of_emails(self):
        findings = classify_column("contact", emails(50))
        self.assertEqual(categories(findings), ["EMAIL"])
        self.assertGreaterEqual(findings[0].confidence, 0.95)
        self.assertEqual(findings[0].sample_size, 50)
        self.assertEqual(findings[0].matched_count, 50)

    def test_column_of_phones_stored_as_integers(self):
        values = [int(p) for p in phones(30)]
        self.assertEqual(categories(classify_column("mobile", values)), ["PHONE"])

    def test_column_of_aadhaar_numbers(self):
        self.assertEqual(categories(classify_column("id_number", aadhaars(20))), ["AADHAAR"])

    def test_mixed_column_reports_both_categories(self):
        values = emails(10) + phones(10)
        self.assertEqual(set(categories(classify_column("contact", values))), {"EMAIL", "PHONE"})

    def test_column_without_pii(self):
        values = ["Bengaluru", "Mumbai", "Delhi", "Pune"] * 10
        self.assertEqual(classify_column("city", values), [])

    def test_empty_values_are_ignored(self):
        values = [None, "", "   "] + emails(5)
        findings = classify_column("email", values)
        self.assertEqual(findings[0].sample_size, 5)
        self.assertEqual(findings[0].matched_count, 5)

    def test_all_empty_column(self):
        self.assertEqual(classify_column("email", [None, "", "  "]), [])
        self.assertEqual(classify_column("email", []), [])

    def test_below_threshold_is_not_reported(self):
        values = emails(2) + ["not an email"] * 18          # 10% match
        self.assertEqual(classify_column("notes", values), [])

    def test_threshold_can_be_changed(self):
        values = emails(2) + ["not an email"] * 18
        findings = classify_column("notes", values, min_ratio=0.05)
        self.assertEqual(categories(findings), ["EMAIL"])

    def test_confidence_drops_when_only_some_values_match(self):
        all_match = classify_column("x", emails(10))[0].confidence
        half_match = classify_column("x", emails(5) + ["hello"] * 5)[0].confidence
        self.assertLess(half_match, all_match)

    def test_column_name_hint_boosts_confidence(self):
        half = emails(5) + ["hello"] * 5
        plain = classify_column("data", half)[0]
        hinted = classify_column("customer_email", half)[0]
        self.assertGreater(hinted.confidence, plain.confidence)
        self.assertIn("column name also suggests", hinted.reason)

    def test_name_hint_works_with_camel_case(self):
        half = emails(5) + ["hello"] * 5
        self.assertIn("column name also suggests", classify_column("customerEmail", half)[0].reason)

    def test_pan_hint_is_not_triggered_by_company(self):
        values = ["ABCPE1234F"] * 5 + ["hello"] * 5
        findings = classify_column("company", values)
        self.assertNotIn("column name also suggests", findings[0].reason)

    def test_name_hint_alone_does_not_create_a_finding(self):
        self.assertEqual(classify_column("email", ["hello", "world"] * 5), [])

    def test_max_sample_limits_how_many_values_are_checked(self):
        findings = classify_column("email", emails(500), max_sample=100)
        self.assertEqual(findings[0].sample_size, 100)

    def test_reason_never_contains_a_value(self):
        values = emails(5)
        for finding in classify_column("email", values):
            for value in values:
                self.assertNotIn(value, finding.reason)

    def test_confidence_is_never_above_one(self):
        for finding in classify_column("email", emails(20)):
            self.assertLessEqual(finding.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()