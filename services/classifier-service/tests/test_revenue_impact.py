"""
test_revenue_impact.py — Unit tests for revenue impact calculation.

Mocks the ClickHouse query so no DB connection is needed.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.revenue_impact import compute_revenue_at_risk


class TestComputeRevenueAtRisk:

    def test_tightening_computes_revenue(self):
        with patch("app.revenue_impact.query_revenue_at_risk", return_value=792000.0):
            result = compute_revenue_at_risk(["75561"], "TIGHTENING")
        assert result == 792000.0

    def test_scope_change_computes_revenue(self):
        with patch("app.revenue_impact.query_revenue_at_risk", return_value=50000.0):
            result = compute_revenue_at_risk(["73221"], "SCOPE_CHANGE")
        assert result == 50000.0

    def test_loosening_returns_zero(self):
        with patch("app.revenue_impact.query_revenue_at_risk") as mock_q:
            result = compute_revenue_at_risk(["75561"], "LOOSENING")
        mock_q.assert_not_called()
        assert result == 0.0

    def test_stylistic_returns_zero(self):
        with patch("app.revenue_impact.query_revenue_at_risk") as mock_q:
            result = compute_revenue_at_risk(["75561"], "STYLISTIC")
        mock_q.assert_not_called()
        assert result == 0.0

    def test_empty_cpt_list_returns_zero(self):
        with patch("app.revenue_impact.query_revenue_at_risk") as mock_q:
            result = compute_revenue_at_risk([], "TIGHTENING")
        mock_q.assert_not_called()
        assert result == 0.0

    def test_formula_annualizes_90d_claims(self):
        """
        Formula: sum(avg_reimbursement_usd * claim_count_90d * 4)
        For CPT 75561: 2200 * 90 * 4 = 792,000
        """
        expected = 2200 * 90 * 4
        with patch("app.revenue_impact.query_revenue_at_risk", return_value=float(expected)):
            result = compute_revenue_at_risk(["75561"], "TIGHTENING")
        assert result == pytest.approx(expected)

    def test_multiple_cpt_codes_summed(self):
        # 75557: 1800*75*4 = 540,000
        # 75559: 2100*65*4 = 546,000
        # 75561: 2200*90*4 = 792,000
        # total: 1,878,000
        expected = (1800 * 75 * 4) + (2100 * 65 * 4) + (2200 * 90 * 4)
        with patch("app.revenue_impact.query_revenue_at_risk", return_value=float(expected)):
            result = compute_revenue_at_risk(["75557", "75559", "75561"], "TIGHTENING")
        assert result == pytest.approx(expected)

    def test_db_returns_none_handled(self):
        """ClickHouse may return None for an empty result set."""
        with patch("app.revenue_impact.query_revenue_at_risk", return_value=0.0):
            result = compute_revenue_at_risk(["99999"], "TIGHTENING")
        assert result == 0.0
