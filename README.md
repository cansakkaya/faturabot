# FaturaBot

An internal Slack bot for a GİB-authorized e-invoice integrator. It answers questions from Customer Service, Sales, and Technical Operations teams by searching a curated set of GİB reference documents in real time.

Built with Python, Slack Bolt (Socket Mode), and the Google Gemini File Search API.

---

## Architecture

```
User (Slack)
     │
     │  posts question in #fatura-bot
     ▼
┌─────────────────────────────────┐
│           bot.py                │
│  Slack Bolt — Socket Mode       │
│                                 │
│  • Receives message event       │
│  • Fetches thread history       │
│    (for follow-up questions)    │
│  • Calls answer_question()      │
└────────────┬────────────────────┘
             │
             │  history: list[dict]
             ▼
┌─────────────────────────────────┐
│         retriever.py            │
│  Gemini generateContent()       │
│                                 │
│  • Builds conversation context  │
│  • Sends question + FileSearch  │
│    tool to gemini-3-flash        │
└────────────┬────────────────────┘
             │
             │  FileSearch tool call
             ▼
┌─────────────────────────────────┐
│   Gemini File Search Store      │
│                                 │
│  7 GİB reference PDFs indexed:  │
│  • e-Arşiv Teknik Kılavuzu      │
│  • e-Fatura Entegrasyon Kılavuzu│
│  • e-Arşiv İptal/İtiraz Kılavuzu│
│  • e-Arşiv Portal Entegrasyon   │
│  • e-Fatura Başvuru Rehberi     │
│  • e-Arşiv Geçiş Rehberi        │
│  • Kritik Hata Kodları          │
└────────────┬────────────────────┘
             │
             │  grounding chunks + answer
             ▼
┌─────────────────────────────────┐
│         retriever.py            │
│                                 │
│  • Extracts page numbers        │
│  • Maps filenames → Slack URLs  │
│  • Builds Kaynaklar footer      │
└────────────┬────────────────────┘
             │
             │  formatted answer (Slack mrkdwn)
             ▼
┌─────────────────────────────────┐
│           bot.py                │
│                                 │
│  • Replies in-thread            │
└─────────────────────────────────┘
     │
     │  answer + clickable PDF sources
     ▼
User (Slack)
```

---

## Features

- **Real-time document search** — answers are grounded in GİB reference PDFs, not model training data
- **Cited sources** — every answer includes clickable links to the source PDFs with page numbers
- **Conversational threads** — follow-up questions in a thread maintain full context
- **Professional tone** — responds in formal business Turkish, tailored for internal teams
- **Incremental PDF management** — add new PDFs anytime; `setup.py` uploads only new files

---

## Project Structure

```
├── bot.py           # Slack Bolt entry point (Socket Mode)
├── retriever.py     # Gemini File Search call + citation builder
├── setup.py         # One-time store creation + incremental PDF upload
├── docs/
│   └── store/       # Source PDF documents
├── .env             # Credentials (not committed)
└── .env.example     # Template for credentials
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in:

```
SLACK_BOT_TOKEN               xoxb-...
SLACK_APP_TOKEN               xapp-...
GEMINI_API_KEY                ...
SLACK_CHANNEL_ID              C...
GEMINI_FILE_SEARCH_STORE_NAME fileSearchStores/...
PDF_LINKS                     filename.pdf:https://slack.com/...,filename2.pdf:https://...
```

### 3. Create the File Search store and upload PDFs

```bash
# First run — creates the store (prints store name, add to .env)
python3 setup.py

# Second run — uploads all PDFs in docs/store/
python3 setup.py

# Adding new PDFs later — skips already-uploaded files
python3 setup.py
```

### 4. Upload PDFs to Slack (for citation links)

Upload each PDF to your Slack workspace, copy the permalink, and add it to `PDF_LINKS` in `.env`.

### 5. Start the bot

```bash
python3 bot.py
```

---

## Slack App Requirements

**Bot Token Scopes:** `channels:history`, `channels:read`, `chat:write`, `files:read`, `files:write`

**Event Subscriptions:** `message.channels`

**Socket Mode:** enabled
