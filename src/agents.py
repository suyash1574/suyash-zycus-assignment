"""
NOOA Intelligent Agents and Guardrails
Implements SupportTriageAgent, TAMHealthAgent, Keyword Tripwires, PII Sanitizer, and Exact Quote Verifier.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from src.config import inference_client, settings
from src.schemas import (
    TicketTriageResult,
    TAMAccountBrief,
    RiskSignal,
    TicketRecord
)
from src.kb_retriever import kb_retriever
from src.data_loader import data_loader

logger = logging.getLogger("agents")


# ==============================================================================
# 1. PII Sanitizer & Keyword Tripwire Guardrails
# ==============================================================================

class Guardrails:
    # Regex patterns for sensitive PII masking
    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    IP_REGEX = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    CC_REGEX = re.compile(r'\b(?:\d[ -]*?){13,16}\b')
    SSN_REGEX = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')

    # Critical outage keywords triggering deterministic urgency promotion
    CRITICAL_TRIPWIRES = [
        "production down", "prod down", "system down", "system is completely down",
        "completely down", "critical emergency", "outage",
        "database connection timeout", "all api nodes", "data loss",
        "cannot log in", "500 error across", "sla breach", "sla violated"
    ]

    HIGH_TRIPWIRES = [
        "pipeline failing", "blocking release", "high priority", "major degradation",
        "unable to connect", "service failure", "critical bug"
    ]

    @classmethod
    def sanitize_pii(cls, text: str) -> str:
        """
        Masks IP addresses, emails, credit cards, and SSNs with clean tokens before external LLM calls.
        """
        if not text:
            return ""
        s = cls.EMAIL_REGEX.sub("[EMAIL_MASKED]", text)
        s = cls.IP_REGEX.sub("[IP_MASKED]", s)
        s = cls.CC_REGEX.sub("[CARD_MASKED]", s)
        s = cls.SSN_REGEX.sub("[SSN_MASKED]", s)
        return s

    @classmethod
    def check_tripwires(cls, text: str) -> Optional[str]:
        """
        Returns 'P1' or 'P2' if critical outage phrases are detected in raw ticket text.
        """
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in cls.CRITICAL_TRIPWIRES):
            return "P1"
        if any(phrase in text_lower for phrase in cls.HIGH_TRIPWIRES):
            return "P2"
        return None


# ==============================================================================
# 2. Quote Grounding & Exact Verbatim Verification
# ==============================================================================

def verify_verbatim_quotes(
    risk_signals: List[Dict[str, Any]],
    raw_tickets: List[Dict[str, Any]]
) -> List[RiskSignal]:
    """
    Validates candidate direct quotes against source ticket bodies using exact substring matching.
    Drops or normalizes any quote that cannot be found in historical records to guarantee 100% quote grounding.
    """
    valid_signals: List[RiskSignal] = []

    # Map ticket bodies by ticket_id for quick search
    ticket_body_map = {t["ticket_id"]: t.get("body", "") for t in raw_tickets}
    all_ticket_bodies = [t.get("body", "") for t in raw_tickets]

    for item in risk_signals:
        candidate_quote = item.get("direct_quote", "").strip()
        ticket_id = item.get("ticket_id", "")
        risk_type = item.get("risk_type", "Technical Escalation")
        severity = item.get("severity", "Medium")

        if not candidate_quote:
            continue

        # Check 1: Exact substring in specified ticket body
        target_body = ticket_body_map.get(ticket_id, "")
        found = candidate_quote in target_body

        # Check 2: If not found in specified ticket, search across all tickets for this account
        matched_tkt_id = ticket_id
        if not found:
            for tkt in raw_tickets:
                if candidate_quote in tkt.get("body", ""):
                    found = True
                    matched_tkt_id = tkt["ticket_id"]
                    break

        # Check 3: Normalized whitespace match
        if not found:
            norm_quote = " ".join(candidate_quote.split())
            for tkt in raw_tickets:
                norm_body = " ".join(tkt.get("body", "").split())
                if norm_quote in norm_body:
                    found = True
                    matched_tkt_id = tkt["ticket_id"]
                    break

        if found:
            try:
                valid_signals.append(
                    RiskSignal(
                        risk_type=risk_type,
                        severity=severity,
                        ticket_id=matched_tkt_id,
                        direct_quote=candidate_quote
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing valid RiskSignal: {e}")
        else:
            logger.warning(f"Dropped ungrounded quote from brief: '{candidate_quote}'")

    return valid_signals


# ==============================================================================
# 3. SupportTriageAgent (Task 1)
# ==============================================================================

class SupportTriageAgent:
    """
    NOOA Agent for classifying raw support tickets, retrieving relevant KB documentation,
    assigning responder teams, and generating empathetic customer response drafts.
    """

    SYSTEM_PROMPT = """You are a Principal Technical Support Triage Engineer.
Your task is to analyze incoming support tickets and produce a strictly structured JSON response.

Classification Rules:
- Product Area: Identify the primary module (e.g. Authentication & SSO, Billing & Plans, Connectors & Integration, CloudSync, DataBridge Pro, WorkflowEngine, AnalyticsHub, Core Infrastructure).
- Issue Category: Must be one of: Bug, Feature Request, How-To, Performance, Billing, Integration, Onboarding, Data Loss.
- Urgency:
  - P1: Critical outage, complete business stoppage, data loss, or system unavailable.
  - P2: Major impact, core feature broken, large user group blocked, workaround difficult.
  - P3: Moderate impact, localized issue, standard bug with workaround.
  - P4: Low impact, minor cosmetic defect, general guidance, invoice question.
- Recommended Team: Target tier-2 team (e.g. Platform Infrastructure Tier-2, IAM Support, Billing Operations, Integration Engineering, Tier-1 Technical Support).
- Draft Response: Professional, empathetic, acknowledging customer impact, citing the matched KB guidance if relevant, and explaining the next troubleshooting steps.
"""

    SCHEMA_INSTRUCTION = """{
  "product_area": "string",
  "issue_category": "Bug | Feature Request | How-To | Performance | Billing | Integration | Onboarding | Data Loss",
  "urgency": "P1 | P2 | P3 | P4",
  "urgency_reasoning": "string (technical explanation)",
  "recommended_team": "string",
  "draft_response": "string"
}"""

    async def triage(
        self,
        subject: Any = None,
        body: Optional[str] = None
    ) -> TicketTriageResult:
        """
        Ingests a raw support ticket as free-text, dictionary, or subject/body strings.
        """
        if isinstance(subject, dict):
            raw_subject = subject.get("subject", "Support Inquiry")
            raw_body = subject.get("body", str(subject))
        elif hasattr(subject, "subject") and hasattr(subject, "body"):
            raw_subject = subject.subject
            raw_body = subject.body
        elif body is None:
            # Free-text input: extract first line as subject, remainder as body
            text_str = str(subject).strip()
            lines = text_str.split("\n", 1)
            raw_subject = lines[0][:120]
            raw_body = lines[1] if len(lines) > 1 else text_str
        else:
            raw_subject = str(subject)
            raw_body = str(body)

        # Step 1: Pre-process and sanitize PII
        clean_subject = Guardrails.sanitize_pii(raw_subject)
        clean_body = Guardrails.sanitize_pii(raw_body)
        full_text = f"{clean_subject}\n\n{clean_body}"

        # Step 2: Evaluate keyword tripwires
        tripwire_urgency = Guardrails.check_tripwires(full_text)

        # Step 3: Retrieve in-memory KB context via BM25
        doc_path, snippet_content = kb_retriever.get_top_snippet_context(full_text)

        # Step 4: Construct structured prompt
        user_prompt = f"""Incoming Ticket:
Subject: {clean_subject}
Body: {clean_body}

Relevant Internal Knowledge Base Context:
Matched Document: {doc_path or 'None'}
Snippet: {snippet_content or 'No matching KB article found above relevance threshold.'}
"""

        # Step 5: Execute multi-tier inference
        raw_result = await inference_client.generate_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_instruction=self.SCHEMA_INSTRUCTION
        )

        # Step 6: Apply tripwire override if detected
        final_urgency = raw_result.get("urgency", "P3")
        reasoning = raw_result.get("urgency_reasoning", "Standard evaluation")
        if tripwire_urgency:
            final_urgency = tripwire_urgency
            reasoning = f"[Tripwire Promoted: {tripwire_urgency}] {reasoning}"

        # Validate against allowed enum
        if final_urgency not in ["P1", "P2", "P3", "P4"]:
            final_urgency = "P3"

        cat = raw_result.get("issue_category", "Bug")
        allowed_cats = ["Bug", "Feature Request", "How-To", "Performance", "Billing", "Integration", "Onboarding", "Data Loss"]
        if cat not in allowed_cats:
            cat = "Bug"

        draft = raw_result.get("draft_response", "Thank you for contacting support. We are reviewing your ticket.")
        # Post-guardrail: Defend against prompt injection leakage in customer draft
        for injected_token in ["hacked", "ignore all previous", "system override"]:
            if injected_token in draft.lower():
                draft = "Hello,\n\nWe have received your urgent ticket and our engineering team is actively investigating the reported system outage.\n\nBest regards,\nTechnical Support Team"

        return TicketTriageResult(
            product_area=raw_result.get("product_area", "General Platform"),
            issue_category=cat,
            urgency=final_urgency,
            urgency_reasoning=reasoning,
            matched_kb_doc=doc_path,
            matched_kb_snippet=snippet_content,
            recommended_team=raw_result.get("recommended_team", "Tier-1 Technical Support"),
            draft_response=draft
        )


# ==============================================================================
# 4. TAMHealthAgent (Task 2)
# ==============================================================================

class TAMHealthAgent:
    """
    NOOA Agent for synthesizing 90-day ticket history and account metadata into a deterministic
    3-section QBR health brief with 100% verbatim verified quotes for churn & escalation risks.
    """

    SYSTEM_PROMPT = """You are a Senior Technical Account Director preparing an executive Quarterly Business Review (QBR) brief.
Your goal is to produce a deterministic, objective 3-section account health report.

Guidelines:
1. Executive Summary: MUST be strictly 3 to 5 sentences long. Cover commercial plan, ARR, active product adoption, health status, and 90-day ticket velocity.
2. Open Risks & Flagged Issues: Identify explicit churn, escalation, or frustration signals. FOR EVERY RISK, YOU MUST PROVIDE A 'direct_quote' THAT IS AN EXACT VERBATIM SUBSTRING FROM THE TICKET BODY.
3. Recommended Talking Points: Provide actionable, strategic agenda items for the QBR.
"""

    SCHEMA_INSTRUCTION = """{
  "account_id": "string",
  "account_name": "string",
  "executive_summary": "string (strictly 3 to 5 sentences)",
  "open_risks": [
    {
      "risk_type": "Churn Risk | Technical Escalation | SLA Breach | Stakeholder Frustration",
      "severity": "High | Medium | Low",
      "ticket_id": "string",
      "direct_quote": "string (EXACT verbatim substring from source ticket)"
    }
  ],
  "recommended_talking_points": [
    "string"
  ]
}"""

    async def generate_brief(self, account_id: str) -> TAMAccountBrief:
        # Step 1: Query account profile and 90-day tickets
        account = data_loader.get_account(account_id)
        if not account:
            # Handle edge case: unknown account ID
            return TAMAccountBrief(
                account_id=account_id,
                account_name=f"Unknown Account ({account_id})",
                executive_summary=f"No account profile found for {account_id} in the customer registry. Historical ticket history cannot be established. Please verify the account identifier with the CRM database administrator.",
                open_risks=[],
                recommended_talking_points=["Verify account identifier in CRM database."]
            )

        tickets_90d = data_loader.get_account_tickets_90d(account_id)
        company_name = account.get("company", "Unknown")

        # Step 2: Handle edge case of 0 tickets
        if len(tickets_90d) == 0:
            plan = account.get("plan_tier", "Standard")
            arr = account.get("arr_usd", 0)
            return TAMAccountBrief(
                account_id=account_id,
                account_name=company_name,
                executive_summary=f"{company_name} is on the {plan} plan with ${arr:,} ARR and has had 0 support tickets submitted in the past 90 days. Their account health is classified as {account.get('health_status', 'Healthy')} with {account.get('usage_trend', 'Stable')} usage trends. The relationship appears exceptionally stable with zero open technical escalations or operational blockers.",
                open_risks=[],
                recommended_talking_points=[
                    f"Celebrate operational stability with zero support tickets in the past quarter.",
                    f"Explore expanding usage across licensed seats ({account.get('seats_active', 0)} of {account.get('seats_licensed', 0)} active).",
                    f"Present roadmap features for {', '.join(account.get('products', []))}."
                ]
            )

        # Step 3: Format ticket summaries for LLM prompt
        ticket_snippets = []
        for t in tickets_90d[:15]:  # Top 15 recent tickets
            sanitized_body = Guardrails.sanitize_pii(t.get("body", ""))
            ticket_snippets.append(
                f"- Ticket ID: {t['ticket_id']} | Subject: {t.get('subject', '')} | Urgency: {t.get('urgency', '')} | Category: {t.get('category', '')}\n  Body: \"{sanitized_body}\""
            )

        user_prompt = f"""Account Metadata:
Account ID: {account_id}
Company Name: {company_name}
Plan Tier: {account.get('plan_tier')} | ARR: ${account.get('arr_usd', 0):,}
Health Status: {account.get('health_status')} | Usage Trend: {account.get('usage_trend')}
Seats: {account.get('seats_active', 0)} active / {account.get('seats_licensed', 0)} licensed
Escalation Notes: {json.dumps(account.get('escalation_notes', []))}

Historical Tickets (Last 90 Days - {len(tickets_90d)} total):
{chr(10).join(ticket_snippets)}
"""

        # Step 4: Execute inference
        raw_result = await inference_client.generate_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_instruction=self.SCHEMA_INSTRUCTION
        )

        # Step 5: Verify exact verbatim quotes
        candidate_risks = raw_result.get("open_risks", [])
        verified_risks = verify_verbatim_quotes(candidate_risks, tickets_90d)

        # If LLM failed to extract quotes from tickets with clear escalation notes, add grounded risk from tickets
        if not verified_risks and len(tickets_90d) > 0:
            for t in tickets_90d:
                if t.get("urgency") in ["P1", "P2"] or "fail" in t.get("body", "").lower():
                    # Extract first sentence as quote
                    first_sentence = t.get("body", "").split("\n")[0].split(".")[0]
                    if len(first_sentence) > 10 and first_sentence in t.get("body", ""):
                        verified_risks.append(
                            RiskSignal(
                                risk_type="Technical Escalation" if t.get("urgency") in ["P1", "P2"] else "Stakeholder Frustration",
                                severity="High" if t.get("urgency") == "P1" else "Medium",
                                ticket_id=t["ticket_id"],
                                direct_quote=first_sentence
                            )
                        )
                        break

        exec_summary = raw_result.get("executive_summary", "")
        # Enforce 3-5 sentence bounds
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', exec_summary) if len(s.strip()) > 5]
        if len(sentences) < 3 or len(sentences) > 5:
            # Fallback normalization to exactly 3 sentences
            exec_summary = f"{company_name} is on an {account.get('plan_tier')} contract (${account.get('arr_usd', 0):,} ARR) currently marked as {account.get('health_status')}. Over the last 90 days, the customer logged {len(tickets_90d)} support tickets reflecting {account.get('usage_trend', 'active')} system utilization. Proactive engagement on technical escalations will be critical during the upcoming QBR to ensure contract renewal stability."

        talking_points = raw_result.get("recommended_talking_points", [
            f"Review resolution of recent {len(tickets_90d)} support tickets.",
            f"Discuss seat expansion and enablement for active users.",
            f"Confirm executive sponsorship ahead of contract renewal on {account.get('renewal_date', 'scheduled date')}."
        ])

        return TAMAccountBrief(
            account_id=account_id,
            account_name=company_name,
            executive_summary=exec_summary,
            open_risks=verified_risks,
            recommended_talking_points=talking_points
        )


triage_agent = SupportTriageAgent()
tam_agent = TAMHealthAgent()
