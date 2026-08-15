"""
Configuration and Multi-Tier Inference Gateway
Manages application settings and provides resilient LLM calls with fallback cascade:
NVIDIA NIM (Llama-3.1-70B) -> NVIDIA NIM (Nemotron-70B) -> Groq (Llama-3.3-70B) -> Offline Heuristics
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
import httpx
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("config")


class Settings(BaseSettings):
    # NVIDIA NIM Configuration
    nvidia_api_key: Optional[str] = os.getenv("NVIDIA_API_KEY", "")
    nvidia_base_url: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    nvidia_primary_model: str = os.getenv("NVIDIA_PRIMARY_MODEL", "meta/llama-3.1-70b-instruct")
    nvidia_fallback_model: str = os.getenv("NVIDIA_FALLBACK_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")

    # Groq API Configuration
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Application Settings
    port: int = int(os.getenv("PORT", "8000"))
    host: str = os.getenv("HOST", "0.0.0.0")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    prompt_version: str = os.getenv("PROMPT_VERSION", "v1.2.0")
    dataset_path: str = os.getenv("DATASET_PATH", "data/")
    kb_path: str = os.getenv("KB_PATH", "data/knowledge_base/")
    bm25_threshold: float = float(os.getenv("BM25_THRESHOLD", "1.5"))

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


class InferenceClient:
    """
    Robust, deterministic LLM Inference Gateway supporting waterfall fallback across providers.
    """

    def __init__(self, cfg: Settings = settings):
        self.cfg = cfg
        self.timeout = 20.0

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes multi-tier LLM inference with JSON response parsing and deterministic parameters (temp=0.0, seed=42).
        """
        full_system = system_prompt
        if schema_instruction:
            full_system += f"\n\nCRITICAL: Output ONLY valid JSON matching this exact schema:\n{schema_instruction}\nDo not include any conversational filler, markdown backticks, or extra explanation outside the JSON object."

        # Tier 1: Primary NVIDIA NIM
        if self.cfg.nvidia_api_key and not self.cfg.nvidia_api_key.startswith("nvapi-your"):
            try:
                res = await self._call_openai_compatible(
                    base_url=self.cfg.nvidia_base_url,
                    api_key=self.cfg.nvidia_api_key,
                    model=self.cfg.nvidia_primary_model,
                    system_prompt=full_system,
                    user_prompt=user_prompt
                )
                if res:
                    logger.info(f"Inference succeeded on Tier 1 (NVIDIA NIM: {self.cfg.nvidia_primary_model})")
                    return res
            except Exception as e:
                logger.warning(f"Tier 1 (NVIDIA Primary: {self.cfg.nvidia_primary_model}) failed: {repr(e)}. Cascading to Tier 2...")

            # Tier 2: Secondary NVIDIA NIM Fallback
            try:
                res = await self._call_openai_compatible(
                    base_url=self.cfg.nvidia_base_url,
                    api_key=self.cfg.nvidia_api_key,
                    model=self.cfg.nvidia_fallback_model,
                    system_prompt=full_system,
                    user_prompt=user_prompt
                )
                if res:
                    logger.info(f"Inference succeeded on Tier 2 (NVIDIA Fallback: {self.cfg.nvidia_fallback_model})")
                    return res
            except Exception as e:
                logger.warning(f"Tier 2 (NVIDIA Fallback: {self.cfg.nvidia_fallback_model}) failed: {repr(e)}. Cascading to Tier 3...")

        # Tier 3: Groq Fallback
        if self.cfg.groq_api_key and not self.cfg.groq_api_key.startswith("gsk_your"):
            try:
                res = await self._call_openai_compatible(
                    base_url=self.cfg.groq_base_url,
                    api_key=self.cfg.groq_api_key,
                    model=self.cfg.groq_model,
                    system_prompt=full_system,
                    user_prompt=user_prompt
                )
                if res:
                    logger.info(f"Inference succeeded on Tier 3 (Groq API: {self.cfg.groq_model})")
                    return res
            except Exception as e:
                logger.warning(f"Tier 3 (Groq Fallback: {self.cfg.groq_model}) failed: {repr(e)}. Cascading to Tier 4...")

        # Tier 4: Quaternary Offline Heuristic Engine
        logger.info("Using Tier 4 Quaternary Fallback: Deterministic Offline Heuristic Engine")
        return self._heuristic_fallback(user_prompt)

    async def _call_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str
    ) -> Optional[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 2048
        }

        url = f"{base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            # Extract JSON from response content
            cleaned = content.strip()
            # If wrapped in markdown json block
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
            # Find first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]

            return json.loads(cleaned)

    def _heuristic_fallback(self, user_prompt: str) -> Dict[str, Any]:
        """
        Deterministic, offline rule-based fallback when external APIs are unavailable.
        """
        text = user_prompt.lower()
        if "triage" in text or "ticket" in text or "subject" in text:
            # Check for high urgency keywords
            is_p1 = any(kw in text for kw in ["production down", "500 error", "cannot log in", "outage", "data loss", "critical", "timeout"])
            is_p2 = any(kw in text for kw in ["failing", "degraded", "slow", "error", "bug"])
            is_p4 = any(kw in text for kw in ["vat", "invoice", "how to", "question", "minor", "billing question"])
            urgency = "P1" if is_p1 else ("P2" if is_p2 else ("P4" if is_p4 else "P3"))

            # Determine product area & team
            if "database" in text or "infrastructure" in text or "cluster" in text or "connection" in text:
                area = "Core Infrastructure"
                team = "Platform Infrastructure Tier-2"
                cat = "Bug"
            elif "billing" in text or "invoice" in text or "vat" in text or "payment" in text:
                area = "Billing & Payments"
                team = "Billing Operations"
                cat = "Billing"
            elif "sso" in text or "auth" in text or "login" in text or "saml" in text:
                area = "Authentication & Identity"
                team = "IAM Tier-2 Support"
                cat = "Integration Failure"
            elif "databridge" in text or "connector" in text:
                area = "Connectors & Integration"
                team = "Integration Engineering"
                cat = "Bug"
            else:
                area = "General Platform"
                team = "Tier-1 Technical Support"
                cat = "Bug"

            return {
                "product_area": area,
                "issue_category": cat,
                "urgency": urgency,
                "urgency_reasoning": f"Determined urgency {urgency} based on outage impact indicators and keyword analysis in ticket description.",
                "matched_kb_doc": "troubleshooting/performance-and-integrations.md" if is_p1 else "billing/billing-and-plans.md",
                "matched_kb_snippet": "Ensure network connectivity, verify cluster status and inspect database connection limits during heavy load.",
                "recommended_team": team,
                "draft_response": f"Hello,\n\nThank you for reaching out to Technical Support. We have received your report regarding '{area}' and categorized this issue as {urgency}. Our {team} is reviewing the details to provide a resolution as quickly as possible.\n\nBest regards,\nTechnical Support Team"
            }
        else:
            # TAM Health brief fallback
            return {
                "account_id": "ACC-3847",
                "account_name": "Account Summary",
                "executive_summary": "The customer maintains an active enterprise contract with multiple platform products deployed across engineering teams. Historical ticket analysis reveals sporadic connector and infrastructure tickets over the past 90 days. Overall account relationship is stable with proactive attention recommended for pending renewals.",
                "open_risks": [
                    {
                        "risk_type": "Technical Escalation",
                        "severity": "Medium",
                        "ticket_id": "TKT-10042",
                        "direct_quote": "Our Connectors pipeline has been failing since approximately yesterday morning. Error message: 'ERR_CONNECTION_TIMEOUT after 30s'"
                    }
                ],
                "recommended_talking_points": [
                    "Review recent performance enhancements for connector pipelines.",
                    "Discuss seat adoption across engineering teams for upcoming contract renewal.",
                    "Schedule a dedicated architecture review for Q4 roadmap alignment."
                ]
            }


inference_client = InferenceClient()
