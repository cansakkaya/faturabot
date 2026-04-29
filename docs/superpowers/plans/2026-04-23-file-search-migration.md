# File Search Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-stage manual retrieval system (index.py + retriever.py) with a single Gemini File Search API call, keeping `bot.py` completely unchanged.

**Architecture:** A new `setup.py` handles one-time store creation and incremental PDF upload (skipping already-uploaded files). A rewritten `retriever.py` exposes the same `answer_question(question) -> str` interface but implements it as a single `generateContent` call with the `FileSearch` tool; grounding chunks from the response are appended as a Markdown blockquote.

**Tech Stack:** Python 3, `google-genai==1.47.0` (`from google import genai`), `python-dotenv`, Slack Bolt (unchanged)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `setup.py` | Create | Store creation + incremental PDF upload |
| `retriever.py` | Replace entirely | `answer_question()` via File Search |
| `.env.example` | Modify | Add `GEMINI_FILE_SEARCH_STORE_NAME` |
| `CLAUDE.md` | Modify | Update key files table and running instructions |
| `index.py` | Delete | Superseded by `setup.py` |
| `docs/indexes/` | Delete | No longer used |
| `bot.py` | Untouched | — |

---

### Task 1: Add `GEMINI_FILE_SEARCH_STORE_NAME` to `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add the new env var**

Open `.env.example`. It currently contains:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
GEMINI_API_KEY=your-gemini-api-key
SLACK_CHANNEL_ID=C_YOUR_CHANNEL_ID
```

Replace with:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
GEMINI_API_KEY=your-gemini-api-key
SLACK_CHANNEL_ID=C_YOUR_CHANNEL_ID
GEMINI_FILE_SEARCH_STORE_NAME=fileSearchStores/your-store-id
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add GEMINI_FILE_SEARCH_STORE_NAME to env example"
```

---

### Task 2: Write `setup.py`

**Files:**
- Create: `setup.py`

`setup.py` is the one-time store creation and incremental sync script. It makes **no** `generateContent` calls — only File Search management API calls.

Logic:
1. Load env. If `GEMINI_FILE_SEARCH_STORE_NAME` is unset/empty → create a store, print its name, and exit with instructions.
2. List existing document display names in the store.
3. For each PDF in `docs/store/`, skip if display name already exists; otherwise upload and poll until done.
4. Print summary.

- [ ] **Step 1: Create `setup.py`**

```python
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()

BASE_DIR = Path(__file__).parent
STORE_DIR = BASE_DIR / "docs" / "store"


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def _existing_display_names(client: genai.Client, store_name: str) -> set[str]:
    names = set()
    for doc in client.file_search_stores.documents.list(parent=store_name):
        if doc.display_name:
            names.add(doc.display_name)
    return names


def _upload_pdf(client: genai.Client, store_name: str, pdf_path: Path) -> None:
    print(f"  Uploading {pdf_path.name}...")
    operation = client.file_search_stores.upload_to_file_search_store(
        file=str(pdf_path),
        file_search_store_name=store_name,
        config={"display_name": pdf_path.name},
    )
    while not operation.done:
        time.sleep(5)
        operation = client.operations.get(operation)
    print(f"  Done: {pdf_path.name}")


def main() -> None:
    client = _client()
    store_name = os.getenv("GEMINI_FILE_SEARCH_STORE_NAME", "").strip()

    if not store_name:
        store = client.file_search_stores.create(
            config={"display_name": "slackbot-knowledge-store"}
        )
        print("File Search store created.")
        print(f"Store name: {store.name}")
        print()
        print("Add this to your .env file:")
        print(f"  GEMINI_FILE_SEARCH_STORE_NAME={store.name}")
        print()
        print("Then re-run setup.py to upload your PDFs.")
        return

    print(f"Using store: {store_name}")
    existing = _existing_display_names(client, store_name)
    print(f"Documents already in store: {len(existing)}")

    pdfs = sorted(STORE_DIR.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in docs/store/")
        return

    uploaded = 0
    skipped = 0
    for pdf_path in pdfs:
        if pdf_path.name in existing:
            print(f"  Skipping {pdf_path.name} (already uploaded)")
            skipped += 1
        else:
            _upload_pdf(client, store_name, pdf_path)
            uploaded += 1

    print(f"\nDone. Uploaded: {uploaded}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add setup.py
git commit -m "feat: add setup.py for File Search store creation and PDF upload"
```

---

### Task 3: Replace `retriever.py`

**Files:**
- Modify: `retriever.py` (full replacement)

The new `retriever.py` exposes one public function: `answer_question(question: str) -> str`. It makes a single `generateContent` call with the `FileSearch` tool and appends the first grounding chunk as a blockquote.

- [ ] **Step 1: Replace `retriever.py` entirely**

```python
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
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

    answer = response.text.strip()

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
        answer = f"{answer}\n\n> {first_text.strip()}"

    return answer
```

- [ ] **Step 2: Commit**

```bash
git add retriever.py
git commit -m "feat: replace retriever with Gemini File Search single-call implementation"
```

---

### Task 4: Delete `index.py` and `docs/indexes/`

**Files:**
- Delete: `index.py`
- Delete: `docs/indexes/` (directory and contents)

- [ ] **Step 1: Delete the files**

```bash
git rm index.py
git rm -r docs/indexes/
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: remove index.py and index files superseded by File Search"
```

---

### Task 5: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

Update the key files table and running instructions to reflect the new structure.

- [ ] **Step 1: Replace the Key Files table**

Find this section in `CLAUDE.md`:

```markdown
## Key Files

| File | Purpose |
|---|---|
| `index.py` | Manual index generator — run once per doc change |
| `retriever.py` | Core retrieval logic: index lookup → section extraction → answer generation |
| `bot.py` | Slack Bolt entry point (Socket Mode) |
| `test_retriever.py` | Tests for retriever functions |
| `docs/*.md` | Knowledge documents |
| `docs/indexes/*.index.md` | LLM-generated index files (auto-created by `index.py`) |
```

Replace with:

```markdown
## Key Files

| File | Purpose |
|---|---|
| `setup.py` | One-time store creation + incremental PDF upload — run after adding new docs |
| `retriever.py` | Single File Search `generateContent` call — exposes `answer_question()` |
| `bot.py` | Slack Bolt entry point (Socket Mode) |
| `docs/store/*.pdf` | Knowledge documents (PDFs) |
```

- [ ] **Step 2: Replace the Architecture section**

Find:

```markdown
## Architecture

Two-stage Gemini retrieval:
1. `find_relevant_sections()` — asks Gemini which `(file, section)` pairs in the indexes are relevant
2. `extract_sections()` — reads those sections verbatim from source `.md` files
3. `generate_answer()` — asks Gemini to answer using only the extracted sections, with a blockquote
```

Replace with:

```markdown
## Architecture

Single-stage Gemini File Search retrieval:
1. `answer_question()` in `retriever.py` — one `generateContent` call with the `FileSearch` tool
2. Gemini semantically searches the File Search store and grounds its answer in retrieved PDF chunks
3. The first grounding chunk is appended to the reply as a Markdown blockquote citation
```

- [ ] **Step 3: Replace the Conventions section entries that reference old files**

Find:

```markdown
- **No live API tests in CI.** Gemini calls are on the free tier (20 req/day). Tests that call Gemini are skipped during development and verified manually.
- **Paths anchored** with `Path(__file__).parent` in both `index.py` and `retriever.py` — never rely on `cwd`.
- **Gemini model singleton** — `_model` in `retriever.py` is initialized once via `_get_model()`.
- **Model name:** `gemini-flash-latest` (not `gemini-1.5-flash` — unavailable on this API key).
- **Do not commit `.env`** — it is gitignored. Use `.env.example` as the template.
```

Replace with:

```markdown
- **No live API tests in CI.** Manual testing only. Do not call Gemini during development.
- **Paths anchored** with `Path(__file__).parent` in `setup.py` — never rely on `cwd`.
- **Gemini client singleton** — `_client` in `retriever.py` is initialized once via `_get_client()`.
- **SDK:** Use `from google import genai` (`google-genai`), not `google-generativeai`.
- **Model name:** `gemini-2.5-flash-lite`.
- **Do not commit `.env`** — it is gitignored. Use `.env.example` as the template.
```

- [ ] **Step 4: Replace the Running section**

Find:

```markdown
## Running

```bash
# Generate/update indexes after adding or changing docs
python3 index.py

# Start the bot
python3 bot.py
```
```

Replace with:

```markdown
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
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for File Search migration"
```

---

### Task 6: Verify the implementation is wired up correctly

No live API calls. Verify statically that everything fits together.

- [ ] **Step 1: Check imports resolve**

```bash
python3 -c "from retriever import answer_question; print('import OK')"
```

Expected output:
```
import OK
```

- [ ] **Step 2: Check setup.py imports resolve**

```bash
python3 -c "import setup; print('import OK')"
```

Expected output:
```
import OK
```

- [ ] **Step 3: Confirm bot.py still imports cleanly**

```bash
python3 -c "
import os
os.environ.setdefault('SLACK_BOT_TOKEN', 'xoxb-fake')
os.environ.setdefault('SLACK_APP_TOKEN', 'xapp-fake')
os.environ.setdefault('SLACK_CHANNEL_ID', 'C000')
os.environ.setdefault('GEMINI_API_KEY', 'fake')
os.environ.setdefault('GEMINI_FILE_SEARCH_STORE_NAME', 'fileSearchStores/fake')
from bot import app
print('bot import OK')
"
```

Expected output:
```
bot import OK
```

- [ ] **Step 4: Commit if any fixups were needed from the above**

```bash
git add -p
git commit -m "fix: resolve import issues found during static verification"
```

(Skip this step if no fixups were needed.)
