import os
import threading
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

_client: Optional[genai.Client] = None
_client_lock = threading.Lock()


def _get_client() -> genai.Client:
    global _client
    with _client_lock:
        if _client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise EnvironmentError("GEMINI_API_KEY is not set.")
            _client = genai.Client(api_key=api_key)
    return _client


def answer_question(question: str) -> str:
    store_name = os.getenv("GEMINI_FILE_SEARCH_STORE_NAME", "").strip()
    if not store_name:
        raise EnvironmentError(
            "GEMINI_FILE_SEARCH_STORE_NAME is not set. Run setup.py first."
        )

    client = _get_client()

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=question,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store_name]
                    )
                )
            ]
        ),
    )

    try:
        answer = response.text.strip()
    except (ValueError, AttributeError):
        return "I couldn't generate an answer. The model did not return a response."

    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks
        first_text = next(
            (
                c.retrieved_context.text
                for c in chunks
                if c.retrieved_context and c.retrieved_context.text
            ),
            None,
        )
    except (AttributeError, IndexError):
        first_text = None

    if first_text:
        quoted = "\n> ".join(first_text.strip().splitlines())
        answer = f"{answer}\n\n> {quoted}"

    return answer
