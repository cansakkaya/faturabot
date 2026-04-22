import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
INDEX_DIR = DOCS_DIR / "indexes"

INDEX_PROMPT = """\
You are given a Markdown document. Produce a structured index of it.

For every section heading (## or ###) in the document, output an entry using exactly this format:

## <Section Heading>
Topics: <comma-separated list of topics covered in this section>
Description: <one or two sentences describing what this section covers>

Output only the index entries. Do not include any introduction, explanation, or the document content itself.
Start with a title line: # Index: {filename}
"""

def generate_index(md_path: Path, model) -> str:
    content = md_path.read_text(encoding="utf-8")
    prompt = INDEX_PROMPT.format(filename=md_path.name) + "\n\n" + content
    response = model.generate_content(prompt)
    index_text = response.text
    if not index_text or not index_text.strip():
        raise ValueError(f"Gemini returned empty content for {md_path.name}")
    return index_text

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set. Check your .env file.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-flash-latest")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    md_files = list(DOCS_DIR.glob("*.md"))

    if not md_files:
        print("No .md files found in docs/")
        return

    successes = 0
    for md_path in md_files:
        print(f"Indexing {md_path.name}...")
        try:
            index_text = generate_index(md_path, model)
            index_path = INDEX_DIR / (md_path.stem + ".index.md")
            index_path.write_text(index_text, encoding="utf-8")
            print(f"  -> Saved {index_path}")
            successes += 1
        except Exception as e:
            print(f"  ERROR: Failed to index {md_path.name}: {e}")

    print(f"Done. {successes}/{len(md_files)} files indexed.")

if __name__ == "__main__":
    main()
