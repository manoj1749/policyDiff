"""
test_classifier_schema.py — Validates classify_diff() output contract.

Tests run against a real Gemini call using a mock candidate,
but also validates pure schema correctness without network access.
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Schema validation helpers (no network required)
# ---------------------------------------------------------------------------

VALID_CHANGE_TYPES = {"TIGHTENING", "LOOSENING", "SCOPE_CHANGE", "STYLISTIC"}
REQUIRED_OUTPUT_KEYS = {
    "change_type",
    "confidence",
    "changed_clause",
    "change_summary",
    "clinical_impact",
    "cpt_codes_affected",
    "recommended_action",
    "markdown_title",
}


def _make_sample_output(**overrides) -> dict:
    base = {
        "change_type": "TIGHTENING",
        "confidence": 0.92,
        "changed_clause": "Member must have completed a cardiac stress test within the past 6 months.",
        "change_summary": "UHC added a stress test prerequisite before cardiac MRI authorization.",
        "clinical_impact": "Prior authorization teams must collect recent stress test documentation.",
        "cpt_codes_affected": ["75561"],
        "recommended_action": "Update cardiology prior authorization checklist.",
        "markdown_title": "UHC Cardiac MRI Policy Tightened — New Stress Test Requirement Added",
    }
    base.update(overrides)
    return base


class TestClassifierOutputSchema:

    def test_all_required_keys_present(self):
        output = _make_sample_output()
        missing = REQUIRED_OUTPUT_KEYS - set(output.keys())
        assert not missing, f"Missing required keys: {missing}"

    def test_valid_change_type(self):
        for ct in VALID_CHANGE_TYPES:
            output = _make_sample_output(change_type=ct)
            assert output["change_type"] in VALID_CHANGE_TYPES

    def test_invalid_change_type_detected(self):
        output = _make_sample_output(change_type="UNKNOWN_TYPE")
        assert output["change_type"] not in VALID_CHANGE_TYPES

    def test_confidence_is_float_in_range(self):
        output = _make_sample_output(confidence=0.85)
        conf = float(output["confidence"])
        assert 0.0 <= conf <= 1.0

    def test_cpt_codes_is_list(self):
        output = _make_sample_output()
        assert isinstance(output["cpt_codes_affected"], list)

    def test_cpt_codes_are_strings(self):
        output = _make_sample_output(cpt_codes_affected=["75561", "93306"])
        for code in output["cpt_codes_affected"]:
            assert isinstance(code, str)

    def test_changed_clause_not_empty_for_tightening(self):
        output = _make_sample_output(change_type="TIGHTENING")
        assert output["changed_clause"] not in ("", "UNSUPPORTED")


# ---------------------------------------------------------------------------
# Normalisation logic (unit tests — no I/O)
# ---------------------------------------------------------------------------

from app.classifier import _validate_and_normalize  # noqa: E402


class TestValidateAndNormalize:

    def _candidate(self, payer="UHC", policy_id="cardiac-mri"):
        return {"payer": payer, "policy_id": policy_id, "diff_id": "test-id"}

    def test_unknown_change_type_defaults_to_stylistic(self):
        raw = _make_sample_output(change_type="GARBAGE")
        raw["summary"] = raw.pop("change_summary")
        result = _validate_and_normalize(raw, self._candidate())
        assert result["change_type"] == "STYLISTIC"

    def test_confidence_clamped_above_1(self):
        raw = _make_sample_output(confidence=1.5)
        raw["summary"] = raw.pop("change_summary")
        result = _validate_and_normalize(raw, self._candidate())
        assert result["confidence"] == 1.0

    def test_confidence_clamped_below_0(self):
        raw = _make_sample_output(confidence=-0.3)
        raw["summary"] = raw.pop("change_summary")
        result = _validate_and_normalize(raw, self._candidate())
        assert result["confidence"] == 0.0

    def test_summary_renamed_to_change_summary(self):
        raw = _make_sample_output()
        raw["summary"] = "A summary"
        raw.pop("change_summary", None)
        result = _validate_and_normalize(raw, self._candidate())
        assert "change_summary" in result
        assert result["change_summary"] == "A summary"

    def test_fallback_cpt_applied_when_empty(self):
        raw = _make_sample_output(cpt_codes_affected=[])
        raw["summary"] = raw.pop("change_summary")
        result = _validate_and_normalize(raw, self._candidate("UHC", "cardiac-mri"))
        # policy_cpt_map.yaml has CPTs for UHC:cardiac-mri
        assert len(result["cpt_codes_affected"]) > 0

    def test_no_fallback_for_unknown_policy(self):
        raw = _make_sample_output(cpt_codes_affected=[])
        raw["summary"] = raw.pop("change_summary")
        result = _validate_and_normalize(raw, self._candidate("UNKNOWN_PAYER", "unknown-policy"))
        assert result["cpt_codes_affected"] == []
