"""
Tests for SupportTriageAgent, PII Sanitizer, and Keyword Tripwires.
"""

import pytest
from src.agents import triage_agent, Guardrails


def test_pii_sanitization():
    raw = "User john.doe@initech.com from 192.168.1.50 with card 4532-1234-5678-9012 reported error."
    sanitized = Guardrails.sanitize_pii(raw)
    assert "[EMAIL_MASKED]" in sanitized
    assert "john.doe@initech.com" not in sanitized
    assert "[IP_MASKED]" in sanitized
    assert "192.168.1.50" not in sanitized
    assert "[CARD_MASKED]" in sanitized
    assert "4532-1234-5678-9012" not in sanitized


def test_keyword_tripwire_critical():
    raw = "Urgent: Production database connection timeout across US-East cluster! Production down!"
    promoted = Guardrails.check_tripwires(raw)
    assert promoted == "P1"


@pytest.mark.asyncio
async def test_triage_p1_outage():
    res = await triage_agent.triage(
        subject="Production Database Connection Timeout across US-East cluster",
        body="All API nodes are returning 500 errors. Customers cannot log in. Immediate escalation needed."
    )
    assert res.urgency == "P1"
    assert res.product_area != ""
    assert res.recommended_team != ""
    assert len(res.draft_response) > 20


@pytest.mark.asyncio
async def test_triage_p4_billing():
    res = await triage_agent.triage(
        subject="Question about updating VAT ID on monthly invoice",
        body="Hi team, we need to update our corporate VAT registration number before the next billing cycle."
    )
    assert res.urgency == "P4"
    assert "billing" in res.issue_category.lower() or "billing" in res.product_area.lower()
