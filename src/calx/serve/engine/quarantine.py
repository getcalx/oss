"""Content quarantine for correction safety.
Scans correction text for suspicious patterns (shell injection, external URLs,
credential references, prompt injection). Flagged content is stored but invisible
to agents and never promoted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


QUARANTINE_PATTERNS = [
    # Shell injection
    re.compile(r'[;&|`$].*(?:rm|curl|wget|bash|sh|python|eval|exec)', re.IGNORECASE),
    # External URLs (whitelist getcalx)
    re.compile(r'https?://(?!github\.com/getcalx)', re.IGNORECASE),
    # Credential references
    re.compile(r'(?:password|secret|token|api.?key|credential)\s*[:=]', re.IGNORECASE),
    # Prompt injection framing
    re.compile(
        r'(?:ignore|forget|disregard)\s+(?:(?:all|previous|above)\s+)*(?:instructions|rules)',
        re.IGNORECASE,
    ),
    # Base64 encoded payloads (50+ chars)
    re.compile(r'[A-Za-z0-9+/]{50,}={0,2}'),
]


@dataclass
class QuarantineResult:
    flagged: bool
    reason: str = ""
    matched_text: str = ""


class QuarantineScanner(Protocol):
    """Protocol for quarantine scanners. Implement this to swap in
    alternative scanning strategies (e.g. LLM-based)."""

    def scan(self, text: str) -> QuarantineResult:
        """Scan text for quarantine-worthy patterns."""
        ...


class RegexQuarantineScanner:
    """Default scanner using regex pattern matching."""

    def __init__(self, patterns: list[re.Pattern[str]] | None = None) -> None:
        self.patterns = patterns if patterns is not None else QUARANTINE_PATTERNS

    def scan(self, text: str) -> QuarantineResult:
        """Scan text for suspicious patterns."""
        for pattern in self.patterns:
            match = pattern.search(text)
            if match:
                return QuarantineResult(
                    flagged=True,
                    reason=f"Pattern match: {pattern.pattern[:50]}",
                    matched_text=match.group()[:100],
                )
        return QuarantineResult(flagged=False)


_default_scanner: QuarantineScanner = RegexQuarantineScanner()


def quarantine_scan(correction_text: str) -> QuarantineResult:
    """Scan correction text for suspicious patterns.

    Delegates to the module-level default scanner (RegexQuarantineScanner).
    Existing callers can continue using this function unchanged.
    """
    return _default_scanner.scan(correction_text)
