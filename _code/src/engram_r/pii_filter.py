"""PII / ID column detection and redaction for EDA safety.

Detects columns likely to contain personally identifiable information
or subject identifiers (common in research datasets) and redacts them.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Universal patterns -- always active regardless of domain profile.
_BASE_ID_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bSSN\b", re.I),
    re.compile(r"\b(first|last|full)[\s_]?name\b", re.I),
    re.compile(r"\bDOB\b", re.I),
    re.compile(r"\bdate[\s_]?of[\s_]?birth\b", re.I),
    re.compile(r"\bemail\b", re.I),
    re.compile(r"\bphone\b", re.I),
    re.compile(r"\baddress\b", re.I),
    re.compile(r"\bzip[\s_]?code\b", re.I),
    re.compile(r"\brecord[\s_]?id\b", re.I),
    re.compile(r"^id$", re.I),
    re.compile(r"[\s_]id$", re.I),
]

# Domain-injected patterns -- populated by register_domain_patterns().
_domain_patterns: list[re.Pattern] = []


def register_domain_patterns(patterns: list[str]) -> None:
    """Compile and register additional PII column patterns from a domain profile.

    Appends to the module-level list so that detect_id_columns() picks
    them up alongside the base patterns.  Idempotent for a given pattern
    string (skips duplicates by raw pattern text).

    Args:
        patterns: Regex strings to compile with re.IGNORECASE.
    """
    existing = {p.pattern for p in _domain_patterns}
    for raw in patterns:
        if raw not in existing:
            _domain_patterns.append(re.compile(raw, re.I))
            existing.add(raw)


def clear_domain_patterns() -> None:
    """Remove all domain-injected patterns (useful for test isolation)."""
    _domain_patterns.clear()


def load_domain_pii_patterns(config_path: Path | str) -> None:
    """Load PII column patterns from the active domain profile.

    Reads the active profile via ``get_active_profile`` and registers
    its ``pii_patterns`` list.  Safe to call multiple times --
    ``register_domain_patterns`` is idempotent.

    Args:
        config_path: Path to ops/config.yaml.
    """
    from engram_r.domain_profile import get_active_profile

    profile = get_active_profile(config_path)
    if profile and profile.pii_patterns:
        register_domain_patterns(profile.pii_patterns)


def detect_id_columns(df: pd.DataFrame) -> list[str]:
    """Detect columns whose names match PII/identifier patterns.

    Args:
        df: Input DataFrame.

    Returns:
        List of column names flagged as potential identifiers.
    """
    all_patterns = _BASE_ID_PATTERNS + _domain_patterns
    flagged = []
    for col in df.columns:
        col_str = str(col)
        for pattern in all_patterns:
            if pattern.search(col_str):
                flagged.append(col)
                break
    return flagged


def redact_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Replace values in specified columns with '[REDACTED]'.

    Returns a copy; does not modify the original DataFrame.

    Args:
        df: Input DataFrame.
        columns: Column names to redact.

    Returns:
        New DataFrame with specified columns redacted.
    """
    df_out = df.copy()
    existing = [c for c in columns if c in df_out.columns]
    for col in existing:
        df_out[col] = "[REDACTED]"
    return df_out


# ---------------------------------------------------------------------------
# Text-level PII scanning (free text, not DataFrames)
# ---------------------------------------------------------------------------

_TEXT_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "email",
    ),
    (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "phone",
    ),
    (re.compile(r"\bMRN[\s:#]?\s?\d+\b", re.I), "MRN"),
]
_REDACTED = "[REDACTED]"


def redact_text(text: str) -> str:
    """Redact PII patterns (SSN, email, phone, MRN) in free text.

    Returns a new string with matches replaced by ``[REDACTED]``.
    """
    for pattern, _label in _TEXT_PII_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


def scrub_outbound(text: str) -> str:
    """Alias for :func:`redact_text`.

    Semantic name for outbound filtering at system boundaries.
    """
    return redact_text(text)


def auto_redact(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Detect and redact ID-like columns automatically.

    Args:
        df: Input DataFrame.

    Returns:
        Tuple of (redacted DataFrame, list of redacted column names).
    """
    flagged = detect_id_columns(df)
    if flagged:
        logger.warning("Auto-redacted columns: %s", flagged)
    return redact_columns(df, flagged), flagged
