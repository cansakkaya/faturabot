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
