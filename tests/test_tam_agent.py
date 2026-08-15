"""
Tests for TAMHealthAgent and Exact Verbatim Quote Verification.
"""

import pytest
from src.agents import tam_agent, verify_verbatim_quotes
from src.data_loader import data_loader


def test_quote_grounding_exact_substring():
    raw_tickets = [
        {"ticket_id": "TKT-101", "body": "Our Connectors pipeline has been failing since yesterday."},
        {"ticket_id": "TKT-102", "body": "Payment was declined due to bank maintenance."}
    ]

    candidate_signals = [
        {
            "risk_type": "Technical Escalation",
            "severity": "High",
            "ticket_id": "TKT-101",
            "direct_quote": "Our Connectors pipeline has been failing since yesterday."
        },
        {
            "risk_type": "Churn Risk",
            "severity": "Medium",
            "ticket_id": "TKT-102",
            "direct_quote": "This is a completely hallucinated quote that was never written."
        }
    ]

    verified = verify_verbatim_quotes(candidate_signals, raw_tickets)
    assert len(verified) == 1
    assert verified[0].ticket_id == "TKT-101"
    assert verified[0].direct_quote == "Our Connectors pipeline has been failing since yesterday."


@pytest.mark.asyncio
async def test_tam_brief_generation_omni_consumer():
    brief = await tam_agent.generate_brief("ACC-3336")
    assert brief.account_id == "ACC-3336"
    assert "Omni Consumer Products" in brief.account_name
    assert len(brief.executive_summary) > 50
    assert len(brief.recommended_talking_points) >= 1

    # Verify all open risk quotes exist in tickets
    tickets_90d = data_loader.get_account_tickets_90d("ACC-3336")
    all_bodies = [t.get("body", "") for t in tickets_90d]
    for risk in brief.open_risks:
        found = any(risk.direct_quote in b for b in all_bodies)
        assert found, f"Ungrounded quote detected: {risk.direct_quote}"


@pytest.mark.asyncio
async def test_tam_brief_generation_zero_tickets():
    brief = await tam_agent.generate_brief("ACC-3033")
    assert brief.account_id == "ACC-3033"
    assert "Polaris Group" in brief.account_name
    assert len(brief.open_risks) == 0
    assert len(brief.recommended_talking_points) >= 1
