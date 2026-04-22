# CLAUDE.md — Slack AI Knowledge Hub

## Project Overview

A Slack bot that listens to a dedicated channel, searches Markdown knowledge documents via LLM-guided indexes, and replies in-thread with Gemini-generated answers that include verbatim source quotes.

## Key Files

| File | Purpose |
|---|---|
| `index.py` | Manual index generator — run once per doc change |
| `retriever.py` | Core retrieval logic: index lookup → section extraction → answer generation |
| `bot.py` | Slack Bolt entry point (Socket Mode) |
| `test_retriever.py` | Tests for retriever functions |
| `docs/*.md` | Knowledge documents |
| `docs/indexes/*.index.md` | LLM-generated index files (auto-created by `index.py`) |

## Architecture

Two-stage Gemini retrieval:
1. `find_relevant_sections()` — asks Gemini which `(file, section)` pairs in the indexes are relevant
2. `extract_sections()` — reads those sections verbatim from source `.md` files
3. `generate_answer()` — asks Gemini to answer using only the extracted sections, with a blockquote

## Conventions

- **No live API tests in CI.** Gemini calls are on the free tier (20 req/day). Tests that call Gemini are skipped during development and verified manually.
- **Paths anchored** with `Path(__file__).parent` in both `index.py` and `retriever.py` — never rely on `cwd`.
- **Gemini model singleton** — `_model` in `retriever.py` is initialized once via `_get_model()`.
- **Model name:** `gemini-flash-latest` (not `gemini-1.5-flash` — unavailable on this API key).
- **Do not commit `.env`** — it is gitignored. Use `.env.example` as the template.

## Environment Variables

```
SLACK_BOT_TOKEN     xoxb-...
SLACK_APP_TOKEN     xapp-...
GEMINI_API_KEY      ...
SLACK_CHANNEL_ID    C...
```

## Running

```bash
# Generate/update indexes after adding or changing docs
python3 index.py

# Start the bot
python3 bot.py
```
