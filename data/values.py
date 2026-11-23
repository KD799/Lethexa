"""
Fake-value generators for Lethexa's synthetic dataset.

EVERYTHING here is made up. Emails use example.* domains (reserved for
documentation), IP addresses come from the documentation ranges, and the
phone / PAN / Aadhaar / card numbers are random values that only follow the
right *format and checksum*. They do not belong to real people.
"""

from __future__ import annotations

import random
import string
from datetime import date, timedelta

from detectors.rules import verhoeff_check_digit

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karthik", "Rahul", "Amit",
    "Suresh", "Vikram", "Ishaan", "Manish", "Nikhil", "Sanjay", "Deepak",
    "Priya", "Ananya", "Diya", "Sneha", "Kavya", "Meera", "Neha", "Pooja",
    "Lakshmi", "Divya", "Anjali", "Riya", "Swati", "Harini", "Tanvi",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Singh", "Das",
    "Patel", "Kumar", "Rao", "Mehta", "Joshi", "Banerjee", "Menon", "Chopra",
    "Kulkarni", "Shetty", "Pillai", "Bose",
]
EMAIL_DOMAINS = ["example.com", "example.org", "example.net"]
CITIES = [
    ("Bengaluru", "Karnataka"), ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"),
    ("Chennai", "Tamil Nadu"), ("Hyderabad", "Telangana"), ("Pune", "Maharashtra"),
    ("Kolkata", "West Bengal"), ("Ahmedabad", "Gujarat"), ("Jaipur", "Rajasthan"),
    ("Kochi", "Kerala"),
]
STREETS = ["MG Road", "Park Street", "Gandhi Nagar", "Residency Road",
           "Lake View Road", "Station Road", "Temple Street", "Hill Road"]
AREAS = ["Indiranagar", "Koramangala", "Andheri", "Salt Lake", "Banjara Hills",
         "Aundh", "Adyar", "Navrangpura", "Vaishali Nagar", "Edappally"]
# Reserved documentation ranges: these IPs never belong to real users.
DOC_IP_PREFIXES = ["203.0.113", "198.51.100", "192.0.2"]


def _digits(rng: random.Random, count: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(count))


def person_name(rng: random.Random) -> tuple[str, str]:
    return rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)


def email(first: str, last: str, number: int, rng: random.Random) -> str:
    return f"{first}.{last}{number}@{rng.choice(EMAIL_DOMAINS)}".lower()


def phone(rng: random.Random) -> str:
    """Indian mobile number in a mix of real-world formats."""
    number = rng.choice("6789") + _digits(rng, 9)
    style = rng.random()
    if style < 0.7:
        return number                      # 9876543210
    if style < 0.9:
        return "+91" + number              # +919876543210
    return number[:5] + " " + number[5:]   # 98765 43210


def pan(rng: random.Random, surname_initial: str) -> str:
    """PAN format: 3 letters + holder type (P = person) + initial + 4 digits + letter."""
    letters = string.ascii_uppercase
    start = "".join(rng.choice(letters) for _ in range(3))
    return f"{start}P{surname_initial.upper()}{_digits(rng, 4)}{rng.choice(letters)}"


def aadhaar(rng: random.Random) -> str:
    """12 digits, first digit 2-9, valid Verhoeff checksum; sometimes written 4-4-4."""
    payload = rng.choice("23456789") + _digits(rng, 10)
    number = payload + verhoeff_check_digit(payload)
    if rng.random() < 0.5:
        return f"{number[:4]} {number[4:8]} {number[8:]}"
    return number


def luhn_check_digit(payload: str) -> str:
    """Digit to append to `payload` so the whole number passes the Luhn check."""
    total = 0
    for i, ch in enumerate(reversed(payload)):
        digit = int(ch)
        if i % 2 == 0:                     # these become every 2nd digit once the check digit is added
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def credit_card(rng: random.Random) -> str:
    """16-digit Visa-style test number with a valid Luhn checksum."""
    payload = "4" + _digits(rng, 14)
    number = payload + luhn_check_digit(payload)
    if rng.random() < 0.5:
        return " ".join(number[i:i + 4] for i in range(0, 16, 4))
    return number


def tracking_number(rng: random.Random) -> str:
    """12 random digits. NOT PII, but about 1 in 10 pass the Aadhaar checksum by chance."""
    return rng.choice("23456789") + _digits(rng, 11)


def payment_ref(rng: random.Random) -> str:
    """16 random digits. NOT PII, but about 1 in 10 pass the Luhn check by chance."""
    return _digits(rng, 16)


def street_address(rng: random.Random) -> str:
    return f"{rng.randint(1, 250)}, {rng.choice(STREETS)}, {rng.choice(AREAS)}"


def pincode(rng: random.Random) -> str:
    return rng.choice("123456789") + _digits(rng, 5)


def ip_address(rng: random.Random) -> str:
    return f"{rng.choice(DOC_IP_PREFIXES)}.{rng.randint(1, 254)}"


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def random_timestamp(rng: random.Random, start: date, end: date) -> str:
    day = random_date(rng, start, end)
    return f"{day} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
