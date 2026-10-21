"""
Run this periodically (weekly, or before a demo/presentation) to see what your knowledge
base is missing, based on real questions students actually asked that the system couldn't
answer.

Usage:
    python kb_gap_report.py
"""
from assistant.report import save_report


def main():
    path = save_report()
    print(f"Report saved to: {path}\n")
    with open(path, "r", encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()