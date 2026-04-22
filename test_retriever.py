# test_retriever.py
from retriever import find_relevant_sections

def test_finds_refund_section():
    results = find_relevant_sections("How do I get a refund?")
    assert len(results) > 0, "Expected at least one result"
    files = [r["file"] for r in results]
    sections = [r["section"] for r in results]
    assert any("sample" in f for f in files), f"Expected sample.md, got {files}"
    assert any("Refund" in s for s in sections), f"Expected Refund section, got {sections}"

def test_returns_empty_for_irrelevant_question():
    results = find_relevant_sections("What is the speed of light?")
    assert results == [], f"Expected empty list, got {results}"

if __name__ == "__main__":
    test_finds_refund_section()
    print("test_finds_refund_section PASSED")
    test_returns_empty_for_irrelevant_question()
    print("test_returns_empty_for_irrelevant_question PASSED")
