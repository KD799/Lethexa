
import re


def detect_pii(text: str):
    findings = []

    patterns = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",

        "PHONE": r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)",

        "GOVERNMENT_ID": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}\b"
    }

    for pii_type, pattern in patterns.items():
        matches = re.findall(pattern, text)

        if matches:
            findings.append({
                "pii_type": pii_type,
                "count": len(matches)
            })

    return {
        "contains_pii": len(findings) > 0,
        "total_pii_categories": len(findings),
        "findings": findings
    }
