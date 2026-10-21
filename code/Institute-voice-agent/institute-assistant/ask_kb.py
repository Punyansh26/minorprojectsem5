"""
Quick retrieval-only testing tool — no LLM, no graph, just "what chunks match this question."
Useful for debugging the knowledge base itself in isolation from agent logic.

Usage:
    python ask_kb.py
    python ask_kb.py --category hostel
"""
import argparse

from assistant.retrieval import retrieve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default=None)
    args = parser.parse_args()

    print("Knowledge base raw retrieval test (Ctrl+C to quit)\n")
    while True:
        try:
            question = input("Q: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break
        if not question:
            continue

        chunks = retrieve(question, category=args.category)
        if not chunks:
            print("No relevant documents found.\n")
            continue
        for c in chunks:
            page_info = f", page {c.page_number}" if c.page_number and c.page_number > 0 else ""
            print(f"\n--- {c.source_file}{page_info} (category: {c.category}, score: {c.score:.3f}) ---")
            print(c.text[:500] + ("..." if len(c.text) > 500 else ""))
        print()


if __name__ == "__main__":
    main()
