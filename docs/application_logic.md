# Main Application Logic & End-to-End Architecture

This document provides a clear, simple, and visual guide to the **Main Application Logic** powering the **SupportTAM AI Platform**.

---

## 🧭 1. High-Level System Workflow

```mermaid
flowchart TD
    User(["Support Engineer / TAM"]) --> UI["Modern 3-Tab Web Dashboard (Port 8000)"]
    
    subgraph FastAPI["FastAPI Application Backend (main.py)"]
        UI -->|1. Submit Ticket| RouteTriage["POST /api/v1/triage"]
        UI -->|2. Request Account Brief| RouteTAM["GET /api/v1/tam-brief/{account_id}"]
        UI -->|3. Trigger Benchmarks| RouteStream["GET /api/v1/stream-evals"]
    end

    subgraph CoreAgents["Core Agent Intelligence (src/agents.py)"]
        RouteTriage --> TriageAgent["SupportTriageAgent"]
        RouteTAM --> TAMAgent["TAMHealthAgent"]
        RouteStream --> EvalHarness["EvaluationHarness (src/eval_harness.py)"]
    end

    subgraph Gateway["4-Tier Resilient Inference Gateway (src/config.py)"]
        TriageAgent & TAMAgent & EvalHarness --> GatewayRouter{"Inference Waterfall Router"}
        GatewayRouter -->|Tier 1| Groq["Groq API (llama-3.3-70b-versatile)"]
        GatewayRouter -->|Tier 2| NIM1["NVIDIA NIM (nvidia/nemotron-3.5-30b)"]
        GatewayRouter -->|Tier 3| NIM2["NVIDIA NIM (meta/llama-3.1-70b)"]
        GatewayRouter -->|Tier 4| Heuristic["Offline Deterministic Heuristic Engine"]
    end

    subgraph Guardrails["Anti-Hallucination & Verification Engines"]
        TriageAgent --> BM25["In-Memory BM25 KB Retriever (T=1.5)"]
        TriageAgent --> RegexPII["Pre-Inference PII Sanitizer & Tripwires"]
        TAMAgent --> QuoteVerifier["Exact Verbatim Substring Quote Verifier"]
    end
```

---

## ⚡ 2. Task 1: Intelligent Ticket Triage Logic

When a raw support ticket arrives via UI or API:

```mermaid
flowchart TD
    Start(["Raw Ticket Input (Free-Text or JSON)"]) --> PII["1. PII Sanitization (Guardrails.sanitize_pii)<br>Masks IPs, Emails, Credit Cards, SSNs"]
    
    PII --> Tripwires{"2. Keyword Tripwire Check<br>(e.g. 'production down', 'database timeout')"}
    Tripwires -->|Outage Detected| SetP1["Elevate Urgency to P1"]
    Tripwires -->|Standard Inquiry| PassThru["Pass to Normal Classification"]
    
    SetP1 & PassThru --> KB["3. In-Memory BM25 Search (src/kb_retriever.py)<br>Scans 9 Markdown Knowledge Base Guides"]
    
    KB --> ScoreCheck{"Top Snippet Score σ >= 1.5?"}
    ScoreCheck -->|Yes| AttachKB["Attach matched_kb_doc & snippet to LLM prompt"]
    ScoreCheck -->|No| ForceNone["Set matched_kb_doc = None<br>(Anti-Hallucination Guard)"]
    
    AttachKB & ForceNone --> Prompt["4. Build Structured Prompt & Call Inference Gateway"]
    Prompt --> GatewayCall["LLM Inference (Temperature: 0.0)"]
    
    GatewayCall --> PostCheck["5. Post-Guardrail Injection Filter<br>Sanitizes draft if prompt injection tokens found"]
    
    PostCheck --> ReturnJSON(["Return TicketTriageResult JSON:<br>• Product Area<br>• Issue Category<br>• Urgency (P1-P4) + Reasoning<br>• Matched KB Doc & Snippet<br>• Recommended Responder Team<br>• Empathetic First-Response Draft"])
```

---

## 📊 3. Task 2: TAM QBR Account Health Summariser Logic

When a Technical Account Manager requests an executive QBR brief:

```mermaid
flowchart TD
    StartTAM(["Account ID (e.g. 'ACC-3336')"]) --> FetchAccount["1. Query Account Profile (data/accounts.json)<br>Company Name, ARR, Plan Tier, Health, Seats"]
    
    FetchAccount --> ExistsCheck{"Account Exists in Registry?"}
    ExistsCheck -->|No| MissingID["Return Graceful Unknown Account Boundary Notice"]
    
    ExistsCheck -->|Yes| FetchTickets["2. Fetch 90-Day Ticket History (src/data_loader.py)<br>Dynamic 90-day time window filtering"]
    
    FetchTickets --> ZeroCheck{"Ticket Count == 0?"}
    ZeroCheck -->|Yes (0 Tickets)| FastZeroBrief["Generate Deterministic Zero-Ticket Stability Brief<br>(No Hallucinated Risks)"]
    
    ZeroCheck -->|No (> 0 Tickets)| PrepContext["3. Sanitize Ticket History & Format Prompt Context"]
    PrepContext --> LLMCall["4. Execute LLM Multi-Doc Synthesis (Temp: 0.0)"]
    
    LLMCall --> QuoteEngine["5. Exact Substring Quote Verification Engine<br>(verify_verbatim_quotes)"]
    
    QuoteEngine --> SubstringMatch{"For every risk quote:<br>Exact substring exists in raw tickets?"}
    SubstringMatch -->|Match Found| KeepQuote["Keep Verified RiskSignal"]
    SubstringMatch -->|Paraphrased / Hallucinated| DropQuote["Drop Ungrounded Quote<br>(Log Warning)"]
    
    KeepQuote & DropQuote --> ReturnBrief(["Return TAMAccountBrief JSON:<br>1. Executive Summary (strictly 3–5 sentences)<br>2. Open Risks (100% Grounded Direct Quotes)<br>3. Recommended QBR Talking Points"])
```

---

## 🔄 4. 4-Tier Waterfall Inference Gateway Logic

Guarantees 100% uptime with sub-second response times:

```mermaid
flowchart TD
    Req(["Inference Request (Prompt + JSON Schema)"]) --> T1{"Tier 1: Groq API<br>(llama-3.3-70b-versatile)"}
    
    T1 -->|Success (200 OK)| Parse1["Extract & Clean JSON"]
    T1 -->|Timeout / 429 Rate Limit| T2{"Tier 2: NVIDIA NIM Primary<br>(nvidia/nemotron-3.5-30b)"}
    
    T2 -->|Success (200 OK)| Parse2["Strip &lt;think&gt; tags & Parse JSON"]
    T2 -->|Timeout / Error| T3{"Tier 3: NVIDIA NIM Fallback<br>(meta/llama-3.1-70b)"}
    
    T3 -->|Success (200 OK)| Parse3["Extract & Clean JSON"]
    T3 -->|Timeout / Error| T4["Tier 4: Deterministic Offline Heuristic Engine<br>(Rule-Based Pattern Matcher)"]
    
    Parse1 & Parse2 & Parse3 & T4 --> ReturnResult(["Return Validated Dictionary to Agent"])
```

---

## 🧪 5. Task 3: Real-Time SSE Benchmark Streaming Logic

Powers the live Evaluation Suite tab:

```mermaid
sequenceDiagram
    autonumber
    participant Browser as UI Browser (Tab 3: Evaluation Suite)
    participant FastAPI as FastAPI Server (/api/v1/stream-evals)
    participant Harness as EvaluationHarness (src/eval_harness.py)
    participant Agents as NOOA Agents (Triage & TAM)

    Browser->>FastAPI: GET /api/v1/stream-evals (EventSource)
    FastAPI->>Harness: stream_all(run_adversarial=True)
    
    loop For each of 10 Benchmark Test Cases
        Harness->>Agents: Execute Test Case (Triage or TAM Brief)
        Agents-->>Harness: Output Result (urgency, quotes, draft)
        Harness->>Harness: Grade with Acceptance Criteria (0.0 to 1.0)
        Harness-->>FastAPI: Yield SSE Event: {"type": "test_progress", "test": ..., "progress": ...}
        FastAPI-->>Browser: Stream Event (text/event-stream)
        Browser->>Browser: Append table row dynamically & tick up scorecards live
    end

    Harness-->>FastAPI: Yield SSE Event: {"type": "test_complete", "summary": ...}
    FastAPI-->>Browser: Stream Completion Event & Close Connection
    Harness->>Harness: Export eval_report.json and eval_report.md
```

---

## 🗄️ 6. Core Data Schemas Summary

```mermaid
classDiagram
    class TicketTriageResult {
        +str product_area
        +str issue_category
        +str urgency (P1-P4)
        +str urgency_reasoning
        +Optional[str] matched_kb_doc
        +Optional[str] matched_kb_snippet
        +str recommended_team
        +str draft_response
    }

    class TAMAccountBrief {
        +str account_id
        +str account_name
        +str executive_summary (3-5 sentences)
        +List~RiskSignal~ open_risks
        +List~str~ recommended_talking_points
    }

    class RiskSignal {
        +str risk_type
        +str severity (High|Medium|Low)
        +str ticket_id
        +str direct_quote (100% verified exact substring)
    }

    class TestCaseResult {
        +str test_id
        +str task_name
        +str test_type
        +bool passed
        +float quality_score (0.0-1.0)
        +str evaluation_notes
    }

    TAMAccountBrief *-- RiskSignal
```
