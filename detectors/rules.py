"""
Lethexa PII detection rules (Step 1: single-value detection).

Give `detect()` one value (a string or number from a database cell) and it
returns a list of Match objects: what kind of PII it looks like, how sure we
are (confidence), and WHY (reason).

Important: this module never stores or logs the value itself. Reasons describe
the rule that fired, not the data.

Categories: EMAIL, PHONE, PAN, AADHAAR, CREDIT_CARD, IP_ADDRESS
"""

from __future__ import annotations
import ipaddress
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    category: str      # e.g. "AADHAAR"
    confidence: float  # 0.0 to 1.0
    reason: str        # human-readable explanation of the rule that fired


# ---------------------------------------------------------------------------
# Checksums
# ---------------------------------------------------------------------------

def luhn_valid(number: str) -> bool:
    """Luhn checksum, used by credit/debit card numbers. `number` = digits only."""
    if not number.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(number)):
        digit = int(ch)
        if i % 2 == 1:          # double every second digit from the right
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


# Verhoeff checksum tables (Aadhaar numbers use this checksum).
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(number: str) -> bool:
    """True if `number` (digits only, check digit included) passes Verhoeff."""
    if not number.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(payload: str) -> str:
    """Return the check digit to append to `payload` (digits only).

    Handy later for the synthetic data generator: build 11 random digits,
    append this digit, and you get a checksum-valid Aadhaar-style number.
    """
    c = 0
    for i, ch in enumerate(reversed(payload)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


# ---------------------------------------------------------------------------
# Individual detectors. Each returns a Match or None.
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^(?:\+91|0)?[6-9]\d{9}$")
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_AADHAAR_RE = re.compile(r"^[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}$")
_CARD_CHARS_RE = re.compile(r"^[\d -]+$")

# 4th letter of a PAN tells the holder type (P = person, C = company, ...).
_PAN_HOLDER_TYPES = "PCHFATBLJG"


def _digits_only(text: str) -> str:
    return re.sub(r"[ -]", "", text)


def detect_email(text: str) -> Match | None:
    if _EMAIL_RE.match(text):
        return Match("EMAIL", 0.98, "matches email address pattern")
    return None


def detect_phone(text: str) -> Match | None:
    compact = _digits_only(text)
    if _PHONE_RE.match(compact):
        if compact.startswith("+91"):
            return Match("PHONE", 0.95, "Indian mobile pattern with +91 country code")
        return Match("PHONE", 0.85, "10-digit Indian mobile pattern (starts with 6-9)")
    return None


def detect_pan(text: str) -> Match | None:
    candidate = text.upper()
    if _PAN_RE.match(candidate):
        if candidate[3] in _PAN_HOLDER_TYPES:
            return Match("PAN", 0.95, "PAN format (5 letters, 4 digits, 1 letter) with valid holder-type letter")
        return Match("PAN", 0.60, "PAN format matches but 4th letter is not a valid holder type")
    return None


def detect_aadhaar(text: str) -> Match | None:
    if _AADHAAR_RE.match(text):
        digits = _digits_only(text)
        if verhoeff_valid(digits):
            return Match("AADHAAR", 0.95, "12 digits, starts with 2-9, passes Verhoeff checksum")
    return None


def detect_credit_card(text: str) -> Match | None:
    if _CARD_CHARS_RE.match(text):
        digits = _digits_only(text)
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            return Match("CREDIT_CARD", 0.85, "13-19 digits that pass the Luhn checksum")
    return None

def detect_ip_address(text: str) -> Match | None:
    if "." not in text and ":" not in text:
        return None
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    return Match("IP_ADDRESS", 0.90, f"valid IPv{address.version} address")

_DETECTORS = (
    detect_email,
    detect_phone,
    detect_pan,
    detect_aadhaar,
    detect_credit_card,
    detect_ip_address,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect(value: object) -> list[Match]:
    """Return all PII matches for one value, most confident first.

    Accepts strings or numbers (phone numbers are often stored as integers).
    None and empty values return [].
    """
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []

    matches = [m for detector in _DETECTORS if (m := detector(text)) is not None]
    return sorted(matches, key=lambda m: m.confidence, reverse=True)