# Design: Migrate Retrieval Layer to Gemini File Search API

**Date:** 2026-04-23  
**Status:** Approved

## Overview

Replace the current two-stage Gemini retrieval system (manual index generation + section extraction) with the Gemini File Search API. The bot's external interface (`answer_question(question) -> str`) stays identical so `bot.py` requires no changes.

## Scope

| File | Action |
|---|---|
| `index.py` | Delete — replaced by `setup.py` |
| `retriever.py` | Replace entirely |
| `setup.py` | New — one-time upload + incremental sync script |
| `.env` / `.env.example` | Add `GEMINI_FILE_SEARCH_STORE_NAME` |
| `CLAUDE.md` | Update to reflect new structure |
| `bot.py` | Untouched |
| `docs/store/*.pdf` | Source documents (unchanged) |
| `docs/indexes/` | No longer used — can be left or deleted |

## Components

### `setup.py` — One-time setup and incremental sync

Run manually after creating the store or adding new PDFs. Never called by the bot at runtime.

**Behaviour:**
1. Reads `GEMINI_API_KEY` and `GEMINI_FILE_SEARCH_STORE_NAME` from `.env`.
2. If `GEMINI_FILE_SEARCH_STORE_NAME` is empty or unset, creates a new File Search store and prints its name so the user can copy it into `.env`, then exits.
3. Lists all documents currently in the store (`documents.list`).
4. For each PDF in `docs/store/`, compares its filename against existing document display names.
5. Skips files already present; uploads new ones via `upload_to_file_search_store`, polling until the operation completes.
6. Prints a per-file summary (skipped / uploaded).

**No Gemini generation calls are made.** Only File Search management API calls (free storage, embedding cost only on new uploads).

### `retriever.py` — Simplified retrieval

Single public function: `answer_question(question: str) -> str`.

**Behaviour:**
1. Initialises `google.genai.Client` once (module-level singleton).
2. Calls `client.models.generate_content` with:
   - model: `gemini-2.5-flash-lite`
   - tool: `FileSearch` pointing at the store name from env
3. Extracts `response.text` as the answer.
4. Extracts the first `grounding_metadata.grounding_chunks[].retrieved_context.text` snippet (if any) and appends it as a Markdown blockquote.
5. Returns the formatted string.

If the store name env var is missing, raises `EnvironmentError` with a clear message. If no grounding chunks are returned, the blockquote is omitted.

**SDK:** `from google import genai` (new `google-genai` SDK, not `google-generativeai`).

## Data Flow

```
User posts in Slack
  → bot.py: answer_question(question)
    → retriever.py: client.models.generate_content(
          model="gemini-2.5-flash-lite",
          contents=question,
          tools=[FileSearch(store_name)]
      )
        ↓
      response.text                          → answer body
      grounding_chunks[0].retrieved_context.text → blockquote
        ↓
      "<answer>\n\n> <source snippet>"
  → bot.py: say(text=answer, thread_ts=thread_ts)
```

## Citation Format

Slack reply structure:

```
<Gemini answer text>

> <verbatim retrieved chunk from grounding_metadata>
```

If multiple grounding chunks are returned, only the first is included as a blockquote. If no chunks are returned, no blockquote is appended.

## Environment Variables

```
GEMINI_API_KEY               # existing
SLACK_BOT_TOKEN              # existing, untouched
SLACK_APP_TOKEN              # existing, untouched
SLACK_CHANNEL_ID             # existing, untouched
GEMINI_FILE_SEARCH_STORE_NAME  # new — e.g. fileSearchStores/abc123
```

## Setup Workflow (after implementation)

```bash
# 1. First time: create the store
python3 setup.py
# -> prints store name, copy into .env as GEMINI_FILE_SEARCH_STORE_NAME

# 2. Upload PDFs (run again whenever new PDFs are added to docs/store/)
python3 setup.py
# -> skips already-uploaded files, uploads new ones

# 3. Start the bot (no change)
python3 bot.py
```

## Constraints

- No tests written (manual testing only).
- No live API calls during implementation.
- `google-generativeai` import in old files is replaced by `google-genai` SDK (`from google import genai`).
- Free tier: embedding cost charged only at upload time; query-time embeddings are free.
