"""Exercise the text helpdesk with a fresh conversation per launch; no login is implied."""
from uuid import uuid4

from langchain_core.messages import HumanMessage

from assistant.config import settings
from assistant.dialogue import normalize_category, valid_email
from assistant.graph import build_graph
from assistant.llm import model_identity


def main():
    """Keep display citations separate from answer_text, which a future TTS adapter can read."""
    print("IIIT-NR Institute Helpdesk\n")
    identity = model_identity()
    print(f"Reasoning: {identity['provider']} / {identity['model']} (no automatic cloud fallback)\n")
    try:
        student_id = input("Student reference (optional; not authentication): ").strip() or "guest"
        while True:
            student_email = input("Email for follow-up (optional): ").strip()
            if not student_email or valid_email(student_email):
                break
            print("Please enter a valid email address, or leave it blank.")
        while True:
            try:
                category = normalize_category(input("Admission category [general/CG]: "))
                break
            except ValueError as error:
                print(error)
    except (KeyboardInterrupt, EOFError):
        print("\nBye.")
        return
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid4())}}
    print(f"\nSession started ({category}). English, Hindi, and Hinglish are supported.")
    print("Type /new for a fresh conversation, /quit to exit.\n")
    try:
        while True:
            question = input("Q: ").strip()
            if not question:
                continue
            if question.casefold() in {"/quit", "/exit", "quit", "exit"}:
                break
            if question.casefold() == "/new":
                config = {"configurable": {"thread_id": str(uuid4())}}
                print("New conversation started.\n")
                continue
            if len(question) > settings.MAX_QUESTION_CHARS:
                print(f"Please keep your question under {settings.MAX_QUESTION_CHARS} characters.\n")
                continue
            try:
                result = graph.invoke({"messages": [HumanMessage(content=question)],
                                       "student_id": student_id, "student_email": student_email,
                                       "student_category": category}, config=config)
            except Exception as error:
                print(f"The session could not complete ({type(error).__name__}). Please try again.\n")
                continue
            print(f"\n{result['answer_text']}")
            if result.get("llm_error"):
                print(result["llm_error"])
            seen = set()
            for source in result.get("sources", []):
                label = source["source_file"]
                if source["page_number"] > 0:
                    label += f", page {source['page_number']}"
                if label not in seen:
                    print(f"  Source: {label}")
                    seen.add(label)
            print()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        # build_graph() owns this connection when no checkpointer is injected.
        graph.checkpointer.conn.close()
    print("\nBye.")


if __name__ == "__main__":
    main()
