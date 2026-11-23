"""
Tests for detectors/rules.py

Run from the repo root:
    python -m unittest discover -s detectors/tests -t . -v
(or `python -m pytest` if you installed pytest)

All sample values below are fake / well-known test values, never real people's data.
"""

import unittest

from detectors.rules import (
    detect,
    luhn_valid,
    verhoeff_check_digit,
    verhoeff_valid,
)


def make_aadhaar(first_11_digits: str) -> str:
    """Build a checksum-valid Aadhaar-style number from 11 digits."""
    return first_11_digits + verhoeff_check_digit(first_11_digits)


def categories(value):
    return [m.category for m in detect(value)]


class ChecksumTests(unittest.TestCase):
    def test_luhn_known_test_cards(self):
        self.assertTrue(luhn_valid("4111111111111111"))   # standard Visa test number
        self.assertTrue(luhn_valid("5500005555555559"))   # standard MasterCard test number

    def test_luhn_rejects_bad_number(self):
        self.assertFalse(luhn_valid("4111111111111112"))

    def test_verhoeff_known_vectors(self):
        self.assertEqual(verhoeff_check_digit("236"), "3")
        self.assertTrue(verhoeff_valid("2363"))
        self.assertTrue(verhoeff_valid("123451"))
        self.assertFalse(verhoeff_valid("2364"))

    def test_make_aadhaar_round_trip(self):
        number = make_aadhaar("23412341234")
        self.assertEqual(len(number), 12)
        self.assertTrue(verhoeff_valid(number))


class EmailTests(unittest.TestCase):
    def test_valid_emails(self):
        for value in ["priya.sharma@example.com", "a_b+tag@mail.co.in", "x@sub.domain.org"]:
            with self.subTest(value=value):
                self.assertIn("EMAIL", categories(value))

    def test_invalid_emails(self):
        for value in ["priya.sharma", "priya@", "@example.com", "priya@example", "hello world@x.com"]:
            with self.subTest(value=value):
                self.assertNotIn("EMAIL", categories(value))


class PhoneTests(unittest.TestCase):
    def test_valid_phones(self):
        for value in ["9876543210", "+919876543210", "+91 98765 43210", "09876543210", 9876543210]:
            with self.subTest(value=value):
                self.assertIn("PHONE", categories(value))

    def test_plus91_has_higher_confidence(self):
        with_code = detect("+919876543210")[0]
        without_code = detect("9876543210")[0]
        self.assertGreater(with_code.confidence, without_code.confidence)

    def test_invalid_phones(self):
        for value in ["1234567890", "5876543210", "98765432", "98765432101234"]:
            with self.subTest(value=value):
                self.assertNotIn("PHONE", categories(value))


class PanTests(unittest.TestCase):
    def test_valid_pan(self):
        match = detect("ABCPE1234F")[0]
        self.assertEqual(match.category, "PAN")
        self.assertGreaterEqual(match.confidence, 0.9)

    def test_lowercase_pan_still_detected(self):
        self.assertIn("PAN", categories("abcpe1234f"))

    def test_pan_with_unusual_holder_letter_is_low_confidence(self):
        match = detect("ABCZE1234F")[0]
        self.assertEqual(match.category, "PAN")
        self.assertLess(match.confidence, 0.7)

    def test_invalid_pan(self):
        for value in ["ABCDE12345", "ABC1E1234F", "ABCPE1234", "ABCPE1234FG"]:
            with self.subTest(value=value):
                self.assertNotIn("PAN", categories(value))


class AadhaarTests(unittest.TestCase):
    def test_valid_aadhaar_plain_and_spaced(self):
        number = make_aadhaar("23412341234")
        spaced = f"{number[:4]} {number[4:8]} {number[8:]}"
        for value in [number, spaced]:
            with self.subTest(value=value):
                self.assertIn("AADHAAR", categories(value))

    def test_checksum_failure_is_not_aadhaar(self):
        number = make_aadhaar("23412341234")
        wrong_last = str((int(number[-1]) + 1) % 10)
        self.assertNotIn("AADHAAR", categories(number[:-1] + wrong_last))

    def test_cannot_start_with_0_or_1(self):
        for first in ["0", "1"]:
            digits = first + "3412341234"
            number = digits + verhoeff_check_digit(digits)
            with self.subTest(first=first):
                self.assertNotIn("AADHAAR", categories(number))

    def test_aadhaar_is_not_mistaken_for_phone(self):
        number = make_aadhaar("91234123412")   # starts with 91 on purpose
        self.assertEqual(categories(number), ["AADHAAR"])


class CreditCardTests(unittest.TestCase):
    def test_valid_cards(self):
        for value in ["4111111111111111", "4111 1111 1111 1111", "5500-0055-5555-5559"]:
            with self.subTest(value=value):
                self.assertIn("CREDIT_CARD", categories(value))

    def test_invalid_cards(self):
        for value in ["4111111111111112", "1234", "41111111111111111111"]:
            with self.subTest(value=value):
                self.assertNotIn("CREDIT_CARD", categories(value))


class GeneralTests(unittest.TestCase):
    def test_empty_and_none(self):
        for value in [None, "", "   "]:
            with self.subTest(value=value):
                self.assertEqual(detect(value), [])

    def test_plain_text_is_not_pii(self):
        for value in ["Bengaluru", "Order delivered", "2026-11-22", "42"]:
            with self.subTest(value=value):
                self.assertEqual(detect(value), [])

    def test_results_sorted_by_confidence(self):
        matches = detect("priya@example.com")
        confidences = [m.confidence for m in matches]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    def test_reason_never_contains_the_value(self):
        value = "priya.sharma@example.com"
        for m in detect(value):
            self.assertNotIn(value, m.reason)


if __name__ == "__main__":
    unittest.main()