from __future__ import annotations

import re

PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)),
    ("phone", re.compile(r"(?:\+?82[- ]?)?0?1[016789][- ]?\d{3,4}[- ]?\d{4}")),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("korean_rrn", re.compile(r"\b\d{6}[- ]?[1-4]\d{6}\b")),
)


def redact_pii(text: str) -> tuple[str, list[str]]:
    redacted = text
    found: list[str] = []
    for name, pattern in PII_PATTERNS:
        if pattern.search(redacted):
            found.append(name)
            redacted = pattern.sub(f"[REDACTED_{name.upper()}]", redacted)
    return redacted, found


def contains_pii(text: str) -> bool:
    return any(pattern.search(text) for _, pattern in PII_PATTERNS)
