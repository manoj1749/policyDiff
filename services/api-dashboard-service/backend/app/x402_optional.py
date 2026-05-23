"""
x402_optional.py — Optional x402 payment-gated PDF export flow.

This module is completely opt-in. If ENABLE_X402=false (default), the
/api/changes/{event_id}/export-pdf endpoint returns a clear message that
the feature is disabled without breaking the rest of the app.

For hackathon demo: any non-empty X-Payment header is treated as mock proof.
Label it clearly in the response.
"""

from __future__ import annotations

import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

ENABLE_X402 = os.getenv("ENABLE_X402", "false").lower() == "true"
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "0x0000000000000000000000000000000000000000")
X402_PRICE_USDC = os.getenv("X402_PRICE_USDC", "2000000")  # 2 USDC in micro-units
USDC_CONTRACT = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"  # Base Sepolia USDC


def is_enabled() -> bool:
    return ENABLE_X402


def build_payment_required_response(event_id: str) -> dict:
    """Return a 402-style response dict when no valid payment header is present."""
    return {
        "error": "Payment required for PDF export",
        "x402": {
            "scheme": "exact",
            "network": "base-sepolia",
            "maxAmountRequired": X402_PRICE_USDC,
            "asset": USDC_CONTRACT,
            "payTo": WALLET_ADDRESS,
            "description": f"PolicyDiff PDF evidence export — event {event_id}",
        },
    }


def verify_payment_header(x_payment: str | None) -> Tuple[bool, str]:
    """
    Verify the X-Payment header.

    For hackathon demo mode: any non-empty header is accepted.
    Returns (is_valid, verification_note).
    """
    if not x_payment:
        return False, "No X-Payment header provided"
    # Demo: accept any non-empty header and flag it clearly
    return True, "DEMO_MOCK_VERIFICATION — not a real blockchain payment"
