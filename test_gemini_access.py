#!/usr/bin/env python3
"""Quick test to verify Gemini API access for a given model and prompt."""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.environ["GEMINI_API_KEY"]
model = os.environ.get("GEMINI_TEST_MODEL", "gemini-2.0-flash")
prompt = os.environ.get("GEMINI_TEST_PROMPT", "Say hello in one sentence.")

client = genai.Client(api_key=api_key)

print(f"Model : {model}")
print(f"Prompt: {prompt}")
print("-" * 40)

response = client.models.generate_content(model=model, contents=prompt)
print(response.text)
