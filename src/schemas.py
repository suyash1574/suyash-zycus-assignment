"""
Data Schemas and Pydantic Contract Models
Defines all request, response, and entity models for Support & TAM AI Platform.
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


# ==============================================================================
# Ingestion Entities
# ==============================================================================

class PrimaryContact(BaseModel):
    name: str = Field(..., description="Full name of primary stakeholder")
    title: str = Field(..., description="Job title / role")


class AccountRecord(BaseModel):
    account_id: str
    company: str
    tam: str
    plan_tier: Literal["Starter", "Professional", "Business", "Enterprise"]
    arr_usd: int
    seats_licensed: int
    seats_active: int
    products: List[str]
    health_status: Literal["Healthy", "At Risk", "Churning", "New"]
    usage_trend: Literal["Increasing", "Stable", "Declining", "Inactive"]
    open_tickets: int
    p1_tickets_last_30d: int
    customer_since: Optional[str] = None
    renewal_date: str
    last_qbr_date: str
    primary_contact: Optional[PrimaryContact] = None
    escalation_notes: List[str] = Field(default_factory=list)
    nps_score: Optional[int] = None
    last_login_days_ago: Optional[int] = None
    integrations_active: List[str] = Field(default_factory=list)
    region: str
    industry: str


class TicketRecord(BaseModel):
    ticket_id: str
    account_id: str
    company: str
    subject: str
    body: str
    product: str
    product_area: str
    category: Literal[
        "Bug", "Feature Request", "How-To", "Performance",
        "Billing", "Integration", "Onboarding", "Data Loss"
    ]
    urgency: Literal["P1", "P2", "P3", "P4"]
    status: Literal["Open", "In Progress", "Pending Customer", "Resolved", "Closed"]
    plan_tier: Literal["Starter", "Professional", "Business", "Enterprise"]
    assigned_agent: Optional[str] = None
    created_at: str
    updated_at: str
    tags: List[str] = Field(default_factory=list)
    channel: Literal["email", "portal", "chat", "phone"]
    satisfaction_score: Optional[int] = None


# ==============================================================================
# Task 1: Ticket Triage Schemas
# ==============================================================================

class TicketTriageRequest(BaseModel):
    subject: str = Field(..., min_length=3, description="Ticket subject line")
    body: str = Field(..., min_length=5, description="Full ticket body description")
    ticket_id: Optional[str] = Field(None, description="Optional mock ticket ID if testing from dataset")


class TicketTriageResult(BaseModel):
    product_area: str = Field(..., description="Identified product module or area")
    issue_category: str = Field(..., description="Identified category: Bug, Feature Request, How-To, Performance, Billing, Integration, Onboarding, Data Loss")
    urgency: Literal["P1", "P2", "P3", "P4"] = Field(..., description="Urgency tier: P1 (Critical), P2 (High), P3 (Medium), P4 (Low)")
    urgency_reasoning: str = Field(..., description="Technical justification for the urgency classification")
    matched_kb_doc: Optional[str] = Field(None, description="Filename or title of matched internal knowledge base document")
    matched_kb_snippet: Optional[str] = Field(None, description="Relevant excerpt from the matched KB document")
    recommended_team: str = Field(..., description="Target engineering or operations escalation team")
    draft_response: str = Field(..., description="Professional, empathetic initial customer reply")


# ==============================================================================
# Task 2: TAM Account Health Brief Schemas
# ==============================================================================

class RiskSignal(BaseModel):
    risk_type: Literal["Churn Risk", "Technical Escalation", "SLA Breach", "Stakeholder Frustration"] = Field(..., description="Classified risk type")
    severity: Literal["High", "Medium", "Low"] = Field(..., description="Impact severity level")
    ticket_id: str = Field(..., description="Source ticket identifier")
    direct_quote: str = Field(..., description="Direct verbatim quote from the source ticket body")


class TAMAccountBrief(BaseModel):
    account_id: str = Field(..., description="Unique customer account identifier")
    account_name: str = Field(..., description="Company name")
    executive_summary: str = Field(..., description="Synthesized summary strictly 3 to 5 sentences long")
    open_risks: List[RiskSignal] = Field(default_factory=list, description="Verified grounded risk indicators")
    recommended_talking_points: List[str] = Field(..., min_length=1, description="Strategic agenda points for QBR")


# ==============================================================================
# Task 3: Evaluation Benchmark Schemas
# ==============================================================================

class TestCaseResult(BaseModel):
    test_id: str
    task_name: Literal["Task 1: Triage", "Task 2: TAM Brief"]
    test_type: Literal["Standard", "Edge", "Adversarial"]
    passed: bool
    quality_score: float = Field(..., ge=0.0, le=1.0)
    evaluation_notes: str


class EvalSummaryReport(BaseModel):
    total_tests: int
    passed_tests: int
    failed_tests: int
    average_score: float
    results: List[TestCaseResult]


class RunEvalRequest(BaseModel):
    run_adversarial: bool = Field(default=True, description="Whether to include edge and adversarial test cases")
