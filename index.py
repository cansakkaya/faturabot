import os
import glob
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-flash-latest")

DOCS_DIR = Path("docs")
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

def generate_index(md_path: Path) -> str:
    content = md_path.read_text(encoding="utf-8")
    prompt = INDEX_PROMPT.format(filename=md_path.name) + "\n\n" + content
    response = model.generate_content(prompt)
    return response.text

def main():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    md_files = list(DOCS_DIR.glob("*.md"))

    if not md_files:
        print("No .md files found in docs/")
        return

    for md_path in md_files:
        print(f"Indexing {md_path.name}...")
        index_text = generate_index(md_path)
        index_path = INDEX_DIR / (md_path.stem + ".index.md")
        index_path.write_text(index_text, encoding="utf-8")
        print(f"  -> Saved {index_path}")

    print("Done.")

if __name__ == "__main__":
    main()
