import os
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
INDEX_DIR = DOCS_DIR / "indexes"

RETRIEVAL_PROMPT = """\
You are a retrieval assistant. Given a set of document indexes and a user question, identify which document sections are relevant to answering the question.

Return ONLY a JSON array. Each element must be an object with:
  "file": the original .md filename (e.g. "sample.md")
  "section": the exact section heading (e.g. "Refund Policy")

If no sections are relevant, return an empty array: []

Do not include any explanation, markdown formatting, or code fences — just the raw JSON array.

User question: {question}

Document indexes:
{indexes}
"""

def _get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set. Check your .env file.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-flash-latest")

def _load_indexes() -> str:
    index_files = sorted(INDEX_DIR.glob("*.index.md"))
    if not index_files:
        return ""
    parts = []
    for idx_path in index_files:
        parts.append(idx_path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)

def find_relevant_sections(question: str) -> list[dict]:
    indexes = _load_indexes()
    if not indexes:
        return []

    model = _get_model()
    prompt = RETRIEVAL_PROMPT.format(question=question, indexes=indexes)
    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown code fences if Gemini wraps the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        results = json.loads(raw)
        if not isinstance(results, list):
            return []
        return [r for r in results if isinstance(r, dict) and "file" in r and "section" in r]
    except json.JSONDecodeError:
        return []
