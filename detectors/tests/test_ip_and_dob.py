import unittest
from datetime import date, datetime

from detectors.column_classifier import classify_column
from detectors.rules import detect


def _categories(value):
    return {m.category for m in detect(value)}


class IpAddressTests(unittest.TestCase):
    def test_valid_ipv4(self):
        self.assertIn("IP_ADDRESS", _categories("192.168.1.10"))

    def test_valid_ipv6(self):
        self.assertIn("IP_ADDRESS", _categories("2001:db8::1"))

    def test_invalid_values_rejected(self):
        for bad in ["256.1.1.1", "1.2.3", "1.2.3.4.5", "10:30:45", "9876543210", "hello"]:
            with self.subTest(bad=bad):
                self.assertNotIn("IP_ADDRESS", _categories(bad))

    def test_reason_does_not_contain_the_value(self):
        match = next(m for m in detect("192.168.1.10") if m.category == "IP_ADDRESS")
        self.assertNotIn("192.168", match.reason)


class DateOfBirthTests(unittest.TestCase):
    DATES = [date(1990, 5, 12), date(1985, 1, 1), date(2001, 7, 30), date(1972, 11, 5)]

    def _categories_for(self, name, values):
        return [f.category for f in classify_column(name, values)]

    def test_flagged_when_name_suggests_birth(self):
        for name in ["date_of_birth", "dob", "birthDate"]:
            with self.subTest(name=name):
                self.assertIn("DATE_OF_BIRTH", self._categories_for(name, self.DATES))

    def test_other_date_columns_not_flagged(self):
        for name in ["created_at", "joined_on", "delivered_at"]:
            with self.subTest(name=name):
                self.assertEqual(classify_column(name, self.DATES), [])

    def test_future_dates_not_flagged(self):
        self.assertEqual(classify_column("dob", [date(2999, 1, 1)] * 3), [])

    def test_strings_and_datetimes_are_accepted(self):
        self.assertIn("DATE_OF_BIRTH", self._categories_for("dob", ["1990-05-12", "12/05/1985"]))
        self.assertIn("DATE_OF_BIRTH", self._categories_for("dob", [datetime(1990, 5, 12, 8, 30)]))

    def test_reason_does_not_contain_a_value(self):
        finding = classify_column("dob", self.DATES)[0]
        self.assertNotIn("1990", finding.reason)