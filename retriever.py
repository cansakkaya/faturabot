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
    matches = re.findall(r'\b(\d+)/(\d+)\b', text)
    pages = []
    for current, total in matches:
        current, total = int(current), int(total)
        # Both sides must be plausible page numbers (1–999) and current ≤ total
        if 1 <= current <= 999 and 1 <= total <= 999 and current <= total:
            pages.append(current)
    return sorted(set(pages))


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
                "If no relevant information is found in the documents, respond with exactly: NO_RESULT:\n"
                "Nothing else. Never use NO_RESULT: if you found relevant information.\n\n"
                "If the user's question has TWO parts and the documents only address ONE of them, "
                "start your response with: PARTIAL_RESULT: <one sentence in Turkish explaining what is NOT covered>\n"
                "Then on the next line, provide what the documents do cover. "
                "Example: PARTIAL_RESULT: Gider pusulası veya iade faturası düzenlenmesi konusunda doğrudan bir yönlendirme bulunmamaktadır.\n"
                "Never use PARTIAL_RESULT: if the documents fully answer the question.\n\n"
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

    is_not_found = answer.startswith("NO_RESULT:")
    if is_not_found:
        answer = "Bu konuyla ilgili bilgiye ulaşamadım. e-Fatura süreçleri hakkında başka sorularında yardımcı olabilirim."

    is_partial = answer.startswith("PARTIAL_RESULT:")
    if is_partial:
        # Extract the "what's missing" sentence and the rest of the answer
        first_newline = answer.find("\n")
        if first_newline != -1:
            missing_part = answer[len("PARTIAL_RESULT:"):first_newline].strip()
            rest = answer[first_newline:].strip()
            answer = f":warning: *{missing_part}*\n\n{rest}"
        else:
            # No body after marker — treat as not found
            answer = "Bu konuyla ilgili bilgiye ulaşamadım. e-Fatura süreçleri hakkında başka sorularında yardımcı olabilirim."
            is_not_found = True
            is_partial = False

    if chunks and not is_not_found:
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
