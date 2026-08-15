# Technical Research & Architecture Decisions: Production-Grade AI for Support & TAM

**Feature**: `001-support-tam-ai`  
**Date**: 2026-08-15  
**Status**: Completed  

---

## 1. Inference Engine & Multi-Tier Gateway Architecture

### Decision
Implement a unified, resilient `InferenceClient` (`src/config.py` / `src/agents.py`) supporting a 4-tier waterfall fallback hierarchy:
1. **Tier 1 (Primary)**: NVIDIA NIM API (`meta/llama-3.1-70b-instruct`) via `https://integrate.api.nvidia.com/v1/chat/completions`
2. **Tier 2 (Secondary Fallback)**: NVIDIA NIM API (`nvidia/llama-3.1-nemotron-70b-instruct`)
3. **Tier 3 (Tertiary Fallback)**: Groq API (`llama-3.3-70b-versatile` or `llama-3.1-70b-versatile`) via `https://api.groq.com/openai/v1/chat/completions`
4. **Tier 4 (Quaternary Fallback)**: Deterministic Heuristic Engine (zero external network dependency, rule-based classification and exact string quote extractor).

### Rationale
- Production SLAs require zero downtime. If NVIDIA NIM hits rate limits (HTTP 429) or transient network timeouts (HTTP 5xx), the client seamlessly shifts to Groq or the local heuristic engine without returning an unhandled error to the user or failing CI evaluation suites.
- Strict determinism is enforced across all tiers by setting `temperature=0.0`, `seed=42`, and parsing outputs into strictly validated Pydantic models (`TicketTriageResult`, `TAMAccountBrief`).

### Alternatives Considered
- *LangChain / LlamaIndex*: Rejected to avoid bloated dependency trees, unneeded abstractions, and opaque prompt mutation. NVIDIA Object-Oriented Agent (NOOA) with native `httpx`/`requests` and Pydantic provides maximum speed, transparency, and determinism.
- *Single Endpoint without Fallback*: Rejected due to high risk of test failures and user disruption during remote API downtime.

---

## 2. In-Memory Retrieval & Knowledge Base Indexing

### Decision
Use `rank_bm25` (BM25Okapi) for in-memory tokenized snippet search over the 9 Markdown knowledge base documents in `knowledge-base/` (`products/`, `troubleshooting/`, `billing/`, `onboarding/`).

### Rationale
- BM25 operates entirely in-memory with sub-millisecond query latency ($< 2\text{ms}$).
- Eliminates heavy vector database dependencies (e.g. Chroma, Pinecone, Milvus), embedding model downloads, and API token overhead.
- Exact keyword matching for error codes (e.g. `ERR_CONNECTION_TIMEOUT`, `HTTP 401`, `SSO_SAML_FAIL`) performs with superior precision compared to embedding distance searches for technical documentation.
- Anti-hallucination threshold gate ($T = 1.5$): If the highest BM25 score falls below $T$, `matched_kb_doc` and `matched_kb_snippet` are set to `None`.

### Alternatives Considered
- *Local Embeddings (sentence-transformers / chromadb)*: Adds ~500MB dependency overhead and 50–100ms vector search latency with negligible gain on 9 domain documents.

---

## 3. Grounding & Exact Verbatim Quote Verification

### Decision
Implement a post-generation quote verification filter (`verify_verbatim_quotes`) in `src/agents.py` that validates all extracted `RiskSignal.direct_quote` strings against the raw historical ticket bodies for the given account.

### Rationale
- LLMs frequently paraphrase or hallucinate quotes when synthesizing summaries.
- In executive QBRs, misattributed or altered quotes can damage client relationships.
- The verification algorithm checks:
  1. Exact substring inclusion: `quote in raw_ticket_body`.
  2. Normalized whitespace / punctuation match as a secondary check.
  3. If neither matches, the risk signal is either pruned or marked with a confidence penalty, strictly guaranteeing $100\%$ quote grounding.

---

## 4. Dataset Ingestion & Dual Format Support

### Decision
Implement `src/data_loader.py` to ingest 500 tickets and 50 accounts directly from `dataset/starter-repo/data/` (or `data/`) supporting both `.json` (`tickets.json`, `accounts.json`) and `.xlsx` (`mock_support_dataset.xlsx` via `pandas` and `openpyxl`).

### Rationale
- Direct JSON loading provides near-instant boot times ($< 50\text{ms}$).
- Excel support satisfies enterprise data delivery requirements and allows analysts to inspect data in spreadsheet software.
- The data loader builds fast in-memory hash maps (`account_id -> account_dict`, `account_id -> list[ticket_dict]`) allowing $O(1)$ lookups for the TAM QBR generator.

---

## 5. Web Interface & Service Layer Design

### Decision
- **Service Layer**: FastAPI with async route handlers and Pydantic v2 schemas.
- **Frontend Architecture**: Clean, accessible Single Page Application (HTML5, Vanilla CSS with CSS custom properties design tokens, and Vanilla JavaScript).
- **Tab Layout**:
  1. *Tab 1: Ticket Triage Studio* (Live textarea, sample ticket loader dropdown, real-time result cards with badge indicators).
  2. *Tab 2: TAM QBR Health Brief* (Account selector, 90-day ticket timeline stats, Executive Summary, Grounded Risk Signals with verbatim quotes, QBR Talking Points).
  3. *Tab 3: Evaluation Suite* (Interactive benchmark runner, progress bar, composite score gauge, detailed results table with pass/fail breakdown).

### Rationale
- Adheres to modern, fluid UI standards without heavy React/Vue build toolchains.
- FastAPI serves static assets and Jinja2-rendered HTML directly on port 8000 for effortless single-command execution (`uvicorn main:app --reload`).
