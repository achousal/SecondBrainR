"""Tests for PII/ID column detection and redaction."""

import pytest
import pandas as pd

from engram_r.pii_filter import (
    auto_redact,
    clear_domain_patterns,
    detect_id_columns,
    redact_columns,
    redact_text,
    register_domain_patterns,
    scrub_outbound,
)

# Clinical patterns matching the bioinformatics profile.
_CLINICAL_PATTERNS = [
    r"\b(subject|patient|participant|person|individual)[\s_]?id\b",
    r"\b(patient|subject|participant)[\s_]?name\b",
    r"\bMRN\b",
    r"\bsample[\s_]?id\b",
]


@pytest.fixture(autouse=True)
def _clean_domain_patterns():
    """Ensure domain patterns are cleared between tests."""
    clear_domain_patterns()
    yield
    clear_domain_patterns()


class TestBasePatterns:
    """Base patterns work without any domain registration."""

    def test_catches_ssn(self):
        df = pd.DataFrame({"SSN": ["123"], "Data": [1]})
        assert "SSN" in detect_id_columns(df)

    def test_catches_email(self):
        df = pd.DataFrame({"Email": ["a@b.com"], "Score": [1]})
        assert "Email" in detect_id_columns(df)

    def test_catches_bare_id(self):
        df = pd.DataFrame({"ID": [1], "Value": [2]})
        assert "ID" in detect_id_columns(df)

    def test_catches_name_columns(self):
        df = pd.DataFrame({"FirstName": ["A"], "LastName": ["B"], "Age": [1]})
        flagged = detect_id_columns(df)
        assert "FirstName" in flagged
        assert "LastName" in flagged

    def test_ignores_safe_columns(self):
        df = pd.DataFrame({"Age": [70], "Metric_A": [0.45], "Diagnosis": ["Active"]})
        assert detect_id_columns(df) == []

    def test_does_not_catch_clinical_without_registration(self):
        df = pd.DataFrame({"PatientName": ["J"], "MRN": ["A1"], "Age": [70]})
        flagged = detect_id_columns(df)
        assert "PatientName" not in flagged
        assert "MRN" not in flagged

    def test_suffix_id_still_caught_by_base(self):
        """Columns ending in _id are caught by the universal suffix pattern."""
        df = pd.DataFrame({"Sample_ID": [1], "Subject_ID": [2], "Age": [3]})
        flagged = detect_id_columns(df)
        assert "Sample_ID" in flagged
        assert "Subject_ID" in flagged


class TestDomainPatterns:
    """Clinical patterns work after domain registration."""

    @pytest.fixture(autouse=True)
    def _register_clinical(self):
        register_domain_patterns(_CLINICAL_PATTERNS)

    def test_catches_subject_id(self):
        df = pd.DataFrame({"SubjectID": [1], "Age": [70]})
        assert "SubjectID" in detect_id_columns(df)

    def test_catches_patient_id(self):
        df = pd.DataFrame({"PatientId": [1], "Score": [5]})
        assert "PatientId" in detect_id_columns(df)

    def test_catches_mrn(self):
        df = pd.DataFrame({"MRN": ["A1"], "Value": [1.0]})
        assert "MRN" in detect_id_columns(df)

    def test_catches_sample_id(self):
        df = pd.DataFrame({"Sample_ID": [1], "Value": [2]})
        assert "Sample_ID" in detect_id_columns(df)

    def test_catches_patient_name(self):
        df = pd.DataFrame({"PatientName": ["John"], "Age": [70]})
        assert "PatientName" in detect_id_columns(df)


class TestRegisterDomainPatterns:
    def test_idempotent(self):
        register_domain_patterns([r"\bMRN\b"])
        register_domain_patterns([r"\bMRN\b"])
        df = pd.DataFrame({"MRN": ["A1"], "Value": [1]})
        flagged = detect_id_columns(df)
        assert flagged.count("MRN") == 1

    def test_clear_removes_patterns(self):
        register_domain_patterns([r"\bMRN\b"])
        clear_domain_patterns()
        df = pd.DataFrame({"MRN": ["A1"], "Value": [1]})
        assert "MRN" not in detect_id_columns(df)


class TestRedactColumns:
    def test_replaces_with_redacted(self):
        df = pd.DataFrame({"SubjectID": ["S001", "S002"], "Age": [70, 68]})
        result = redact_columns(df, ["SubjectID"])
        assert all(result["SubjectID"] == "[REDACTED]")
        assert list(result["Age"]) == [70, 68]

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"SubjectID": ["S001"], "Age": [70]})
        redact_columns(df, ["SubjectID"])
        assert df["SubjectID"].iloc[0] == "S001"

    def test_handles_missing_column(self):
        df = pd.DataFrame({"Age": [70]})
        result = redact_columns(df, ["Nonexistent"])
        assert list(result.columns) == ["Age"]


class TestAutoRedact:
    @pytest.fixture(autouse=True)
    def _register_clinical(self):
        register_domain_patterns(_CLINICAL_PATTERNS)

    def test_detects_and_redacts(self):
        df = pd.DataFrame({
            "SubjectID": ["S001"],
            "PatientName": ["John"],
            "Age": [70],
            "Metric_A": [0.45],
        })
        result, flagged = auto_redact(df)
        assert "SubjectID" in flagged
        assert "PatientName" in flagged
        assert result["SubjectID"].iloc[0] == "[REDACTED]"
        assert result["Age"].iloc[0] == 70

    def test_no_pii_returns_unchanged(self):
        df = pd.DataFrame({"Age": [70], "Score": [5.0]})
        result, flagged = auto_redact(df)
        assert flagged == []
        assert result.equals(df)


class TestRedactText:
    """Tests for free-text PII redaction."""

    def test_redacts_ssn(self):
        assert redact_text("SSN is 123-45-6789") == "SSN is [REDACTED]"

    def test_redacts_email(self):
        result = redact_text("Contact alice@example.com for details")
        assert "[REDACTED]" in result
        assert "alice@example.com" not in result

    def test_redacts_phone(self):
        result = redact_text("Call (555) 123-4567 today")
        assert "[REDACTED]" in result
        assert "555" not in result

    def test_redacts_mrn(self):
        result = redact_text("Patient MRN: 12345 enrolled")
        assert "[REDACTED]" in result
        assert "12345" not in result

    def test_preserves_clean_text(self):
        clean = "Factor-X trans-signaling drives chronic response in test regions"
        assert redact_text(clean) == clean

    def test_empty_string(self):
        assert redact_text("") == ""

    def test_multiple_patterns(self):
        text = "Email: a@b.com, SSN: 111-22-3333, MRN#4567"
        result = redact_text(text)
        assert "a@b.com" not in result
        assert "111-22-3333" not in result
        assert "4567" not in result
        assert result.count("[REDACTED]") == 3

    def test_does_not_redact_elo_scores(self):
        """Elo scores like 1250.0 should not be falsely redacted."""
        text = "Hypothesis H-001 has an Elo of 1250.0 after 8 matches"
        assert redact_text(text) == text

    def test_scrub_outbound_is_alias(self):
        """scrub_outbound is a thin alias for redact_text."""
        text = "Contact alice@example.com"
        assert scrub_outbound(text) == redact_text(text)
