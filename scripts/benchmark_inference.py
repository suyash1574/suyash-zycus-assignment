"""
Benchmark inference latency across NVIDIA NIM and Groq API.
"""

import time
import httpx
import json
from dotenv import load_dotenv
import os
load_dotenv()

nv_key = os.getenv("NVIDIA_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

prompt = "Analyze ticket: Database connection timeout in US-East cluster. Output JSON with urgency P1 and reason."

# 1. Test Groq
t0 = time.time()
r_groq = httpx.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
    json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
    timeout=10.0
)
t_groq = time.time() - t0
print(f"Groq API status: {r_groq.status_code}, latency: {t_groq:.2f}s")
if r_groq.status_code == 200:
    print("Groq response snippet:", r_groq.json()["choices"][0]["message"]["content"][:100])

# 2. Test NVIDIA NIM
t0 = time.time()
r_nv = httpx.post(
    "https://integrate.api.nvidia.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {nv_key}", "Content-Type": "application/json"},
    json={"model": "nvidia/nemotron-3.5-lightning-30b-a3b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
    timeout=10.0
)
t_nv = time.time() - t0
print(f"NVIDIA NIM status: {r_nv.status_code}, latency: {t_nv:.2f}s")
if r_nv.status_code == 200:
    print("NVIDIA response snippet:", r_nv.json()["choices"][0]["message"]["content"][:100])
