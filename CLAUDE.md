# CLAUDE.md — Slack AI Knowledge Hub

## Project Overview

A Slack bot that listens to a dedicated channel, searches PDF knowledge documents via the Gemini File Search API, and replies in-thread with Gemini-generated answers that include verbatim source quotes.

## Key Files

| File | Purpose |
|---|---|
| `setup.py` | One-time store creation + incremental PDF upload — run after adding new docs |
| `retriever.py` | Single File Search `generateContent` call — exposes `answer_question()` |
| `bot.py` | Slack Bolt entry point (Socket Mode) |
| `docs/store/*.pdf` | Knowledge documents (PDFs) |

## Architecture

Single-stage Gemini File Search retrieval:
1. `answer_question()` in `retriever.py` — one `generateContent` call with the `FileSearch` tool
2. Gemini semantically searches the File Search store and grounds its answer in retrieved PDF chunks
3. The first grounding chunk is appended to the reply as a Markdown blockquote citation

## Conventions

- **No live API tests in CI.** Manual testing only. Do not call Gemini during development.
- **Paths anchored** with `Path(__file__).parent` in `setup.py` — never rely on `cwd`.
- **Gemini client singleton** — `_client` in `retriever.py` is initialized once via `_get_client()`.
- **SDK:** Use `from google import genai` (`google-genai`), not `google-generativeai`.
- **Model name:** `gemini-2.5-flash-lite`.
- **Do not commit `.env`** — it is gitignored. Use `.env.example` as the template.

## Environment Variables

```
SLACK_BOT_TOKEN               xoxb-...
SLACK_APP_TOKEN               xapp-...
GEMINI_API_KEY                ...
SLACK_CHANNEL_ID              C...
GEMINI_FILE_SEARCH_STORE_NAME fileSearchStores/...
```

## Running

```bash
# First time: create the File Search store (prints store name to copy into .env)
python3 setup.py

# Add GEMINI_FILE_SEARCH_STORE_NAME to .env, then upload PDFs
python3 setup.py

# When adding new PDFs to docs/store/, re-run to upload only new files
python3 setup.py

# Start the bot
python3 bot.py
```
