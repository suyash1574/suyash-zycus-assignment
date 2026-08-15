# Quickstart & Validation Guide: Support & TAM AI Platform

**Feature**: `001-support-tam-ai`  
**Date**: 2026-08-15  

---

## 1. Prerequisites & Environment Setup

- **Python Version**: Python 3.10+
- **Environment Variables**: Create `.env` from `.env.example`:
  ```bash
  # Optional: NVIDIA NIM API Key (Falls back to Groq or Offline Heuristics if omitted)
  NVIDIA_API_KEY=nvapi-your-key-here
  # Optional: Groq API Key as secondary remote fallback
  GROQ_API_KEY=gsk_your-key-here
  ```

### Installation
```bash
pip install -r requirements.txt
```

---

## 2. Launching the Web Dashboard & API Server

Start the FastAPI application with Uvicorn:
```bash
python main.py
# Or:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Open your browser at `http://localhost:8000/`.

---

## 3. End-to-End Validation Scenarios

### Scenario 1: Real-Time Ticket Triage (Task 1)
- **Action**: In Tab 1 of the web dashboard, select a sample ticket (e.g. *P1 Outage: DataBridge Connection Timeout*) and click **"Analyze & Triage"**.
- **Or via cURL**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/triage \
    -H "Content-Type: application/json" \
    -d '{
      "subject": "Production Database Connection Timeout across US-East cluster",
      "body": "All API nodes are returning 500 errors. Customers cannot log in. Immediate escalation needed."
    }'
  ```
- **Expected Outcome**:
  - `urgency`: `"P1"`
  - `recommended_team`: `"Platform Infrastructure Tier-2"` or `"Core Infrastructure"`
  - `matched_kb_doc`: Identified relevant troubleshooting document
  - `draft_response`: Empathetic initial customer message

---

### Scenario 2: TAM QBR Health Brief Generation (Task 2)
- **Action**: In Tab 2 of the web dashboard, select `ACC-3847 (Initech)` and click **"Generate TAM Brief"**.
- **Or via cURL**:
  ```bash
  curl -X GET http://localhost:8000/api/v1/tam-brief/ACC-3847
  ```
- **Expected Outcome**:
  - `executive_summary`: 3–5 sentences summarizing account tier ($240k ARR), health status (At Risk), and 90-day ticket history.
  - `open_risks`: Grounded risk signals where `direct_quote` matches verbatim from ticket `TKT-10042`.
  - `recommended_talking_points`: Actionable agenda items for the QBR.

---

### Scenario 3: Automated Evaluation Suite (Task 3)
- **Action**: In Tab 3 of the web dashboard, click **"Run Evaluation Benchmark"**.
- **Or via CLI/cURL**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/run-evals -H "Content-Type: application/json" -d '{}'
  # Or run directly via pytest:
  pytest -v
  ```
- **Expected Outcome**:
  - All 10 benchmark test cases (standard, edge, adversarial) execute.
  - Generates `eval_report.json` in repository root.
  - Composite quality score $\ge 0.80$ (Target: $> 0.90$).
