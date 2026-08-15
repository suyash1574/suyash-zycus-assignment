"""
Live API Verification Script
Tests NVIDIA NIM and Groq API endpoints using the configured .env keys.
"""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.config import InferenceClient, settings

async def main():
    print("Testing live inference through InferenceClient...")
    client = InferenceClient(settings)
    
    res = await client.generate_json(
        system_prompt="You are a principal support triage engineer.",
        user_prompt="Ticket: Database connection pool exhausted causing 500 errors in US-East.",
        schema_instruction='{"product_area": "string", "urgency": "P1", "reasoning": "string"}'
    )
    print("Live API Response:")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
