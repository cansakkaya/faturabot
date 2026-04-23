import os
import re
import threading
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

_client: genai.Client | None = None
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


def _parse_pdf_links() -> dict[str, str]:
    """Parse PDF_LINKS env var: 'filename.pdf:url,filename2.pdf:url2'"""
    raw = os.getenv("PDF_LINKS", "")
    links = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            filename, url = entry.split(":", 1)
            links[filename.strip()] = url.strip()
    return links


def _extract_pages(text: str) -> list[int]:
    """Extract page numbers from patterns like '8/21' in chunk text."""
    matches = re.findall(r'\b(\d+)/\d+\b', text)
    return sorted(set(int(m) for m in matches))


def answer_question(history: list[dict]) -> str:
    store_name = os.getenv("GEMINI_FILE_SEARCH_STORE_NAME", "").strip()
    if not store_name:
        raise EnvironmentError(
            "GEMINI_FILE_SEARCH_STORE_NAME is not set. Run setup.py first."
        )

    client = _get_client()

    # Build conversation context for the system instruction
    context_lines = []
    for turn in history[:-1]:  # everything except the last message
        prefix = "User" if turn["role"] == "user" else "Assistant"
        context_lines.append(f"{prefix}: {turn['text']}")

    conversation_context = ""
    if context_lines:
        conversation_context = (
            "\n\nPrevious conversation:\n" + "\n".join(context_lines)
        )

    # Last message is the current question
    question = history[-1]["text"]

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are FaturaBot, an internal knowledge assistant for a Turkish e-invoice solution provider "
                "authorized by the Turkish Revenue Administration (GİB). "
                "Your users are internal teams — Customer Service, Sales, and Technical Operations — "
                "who are experienced professionals in e-invoice regulations and technical integrations.\n\n"
                "Always respond in Turkish. Use formal but plain business Turkish. "
                "Do not translate technical terms (API, endpoint, UBL, etc.) into Turkish. "
                "Never use phrases like 'Belgeye göre...' or 'Dokümanda belirtildiği üzere...' — state information directly. "
                "Avoid unnecessary filler or courtesy phrases.\n\n"
                "Answer strictly from the provided reference documents. "
                "Never fabricate or infer information not explicitly found in the documents. "
                "If no relevant information is found, respond only with: "
                "\"Bu konu ile ilgili şu anda bilgi veremiyorum. Kendimi geliştirmeye devam ediyorum\"\n\n"
                "Format all responses using Slack mrkdwn syntax:\n"
                "- Bold: *text* (single asterisks only, never double)\n"
                "- Italic: _text_\n"
                "- Inline code: `code`\n"
                "- Code block: ```code```\n"
                "- Bullet list: lines starting with • or -\n"
                "- Link: <https://example.com|display text>\n"
                "- Never use ## or ### headers; use *bold text* instead.\n"
                "- Never use **double asterisks**."
                + conversation_context
            ),
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store_name]
                    )
                )
            ],
        ),
    )

    try:
        answer = response.text.strip()
    except (ValueError, AttributeError):
        return "Şu anda yanıt veremiyorum. Lütfe daha sonra tekrar dene."

    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks
        chunks = [c for c in chunks if c.retrieved_context and c.retrieved_context.title]
    except (AttributeError, IndexError):
        chunks = []

    NO_RESULT_MARKER = "Bu konu ile ilgili şu anda bilgi veremiyorum"
    answer_is_from_docs = chunks and NO_RESULT_MARKER not in answer and any(
        word in answer
        for c in chunks
        if c.retrieved_context and c.retrieved_context.text
        for word in c.retrieved_context.text.split()[:20]
        if len(word) > 5
    )
    if answer_is_from_docs:
        pdf_links = _parse_pdf_links()

        # Collect unique sources with their page numbers
        sources: dict[str, list[int]] = {}
        for c in chunks:
            title = c.retrieved_context.title
            pages = _extract_pages(c.retrieved_context.text or "")
            if title not in sources:
                sources[title] = []
            sources[title].extend(pages)

        # Deduplicate and sort pages per source
        for title in sources:
            sources[title] = sorted(set(sources[title]))

        # Build footer lines
        footer_lines = []
        for title, pages in sources.items():
            url = pdf_links.get(title)
            display_name = title.replace("_", " ").replace(".pdf", "")
            page_str = f" — Sayfa {', '.join(str(p) for p in pages)}" if pages else ""
            if url:
                footer_lines.append(f"• <{url}|{display_name}>{page_str}")
            else:
                footer_lines.append(f"• {display_name}{page_str}")

        answer = answer + "\n\n*Kaynaklar:*\n" + "\n".join(footer_lines)

    return answer
