# Handoff: Slack AI Knowledge Hub

## What This Project Is

A Slack bot (FaturaBot) that listens to a dedicated Slack channel (`#fatura-bot`), searches PDF knowledge documents via the Gemini File Search API, and replies in-thread with Gemini-generated answers. Built with Python, Slack Bolt (Socket Mode), `google-genai` SDK.

## Current State

All code is in `/Users/cansuakkaya/Desktop/Slackbot/`. The bot is fully functional and running.

## Key Files

| File | Purpose |
|---|---|
| `bot.py` | Slack Bolt entry point (Socket Mode). Fetches thread history for conversational context. |
| `retriever.py` | Calls Gemini File Search API. `answer_question(history)` is the main function. |
| `setup.py` | One-time store creation + incremental PDF upload. Run after adding new PDFs. |
| `docs/store/*.pdf` | Source PDFs. Currently one file: `e-Arsiv_Uygulamalari_Iptal_Ihtar_Itiraz_Bildirim_Kilavuzu_V.1.1.pdf` |
| `.env` | Real credentials — DO NOT COMMIT |

## Architecture

1. User posts in `#fatura-bot` channel
2. `bot.py` receives the event, fetches full thread history if it's a reply
3. Passes history as `list[dict]` to `answer_question(history)` in `retriever.py`
4. `retriever.py` builds conversation context into system_instruction, calls `gemini-2.5-flash-lite` with FileSearch tool
5. If grounding chunks are returned → appends blockquote + source filename
6. Bot replies in-thread

## Environment Variables (all set in .env)

```
GEMINI_API_KEY=AIzaSyDA3M37pdi6uBVSaSr9nlqkagmklslH2I4
GEMINI_FILE_SEARCH_STORE_NAME=fileSearchStores/slackbotknowledgestore-oxytixo0tayl
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C0AUTH9M2SW   ← this is #fatura-bot channel
```

## Slack App Configuration

- App name: **FaturaBot** (was "Demo App", renamed "KnowledgeBot", final name "FaturaBot")
- Workspace: **Cansu**
- Socket Mode: **enabled**
- Bot Token Scopes: `channels:history`, `channels:read`, `chat:write`
- Event Subscriptions: `message.channels` enabled
- Bot is invited to `#fatura-bot` channel

## Billing

- Google AI Studio billing is **enabled** (upgraded from free tier during this session)
- Free tier limit was 20 req/day — now on paid tier

## CRITICAL PENDING ISSUE: Citations Not Working

**The main unresolved problem:** `gemini-2.5-flash-lite` does **not** return `grounding_metadata.grounding_chunks`. This means:
- The bot answers correctly for questions covered by the PDF ✅
- But no blockquote citation or source filename is appended ❌
- The bot sometimes answers from its own training data instead of the PDF ❌

**Root cause confirmed by testing:**
```python
# gemini-2.5-flash-lite → always returns 0 grounding chunks
# gemini-2.5-flash → returns 5 grounding chunks with PDF title ✅
```

**The fix:** Switch model from `gemini-2.5-flash-lite` to `gemini-2.5-flash` in `retriever.py` line 49.

**Why it's not done yet:** `gemini-2.5-flash` was returning 503 (high demand / overloaded) at the end of this session. It was working earlier today — this is a temporary Gemini infrastructure issue.

**What to do in the next session:**
1. Test if `gemini-2.5-flash` is available:
```bash
python3 -c "
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
store_name = os.getenv('GEMINI_FILE_SEARCH_STORE_NAME')
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='e-Arşiv fatura iptal talebi nasıl oluşturulur?',
    config=types.GenerateContentConfig(
        tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))],
    ),
)
chunks = response.candidates[0].grounding_metadata.grounding_chunks
print('chunks:', len(chunks))
print(response.text[:200])
"
```
2. If it works (chunks > 0), change line 49 in `retriever.py`:
   - From: `model="gemini-2.5-flash-lite",`
   - To: `model="gemini-2.5-flash",`
3. Restart `python3 bot.py` and test in Slack

## How to Start the Bot

```bash
cd /Users/cansuakkaya/Desktop/Slackbot
python3 bot.py
```

Expected output:
```
Bot is running. Listening for messages...
⚡ Bolt app is running!
```

## Conversational Thread Context

`bot.py` now supports follow-up questions in threads. When a reply is detected (`thread_ts` present), it fetches the full thread history via `conversations_replies` and passes it to `retriever.py` as conversation context embedded in the system instruction.

## Adding More PDFs

The bot currently only knows about e-Arşiv cancellation/objection processes. To expand:
1. Add PDF(s) to `docs/store/`
2. Run `python3 setup.py` — it skips already-uploaded files, uploads only new ones
