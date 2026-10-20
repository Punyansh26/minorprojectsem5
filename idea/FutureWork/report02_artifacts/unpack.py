#!/usr/bin/env python3
"""Unpack the fenced **File:** blocks of REPORT_02 into this directory.

Reads ../REPORT_02_LATENCY_COST_MODEL_AND_METRICS.md, finds each block whose
heading line is  **File:** `name`  immediately followed by a fenced code block,
and writes it next to this script. Idempotent.
"""
import pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
REPORT = HERE.parent / "REPORT_02_LATENCY_COST_MODEL_AND_METRICS.md"
text = REPORT.read_text(encoding="utf-8")
pattern = re.compile(r"\*\*File:\*\*\s*`([^`]+)`\s*\n+```[a-zA-Z0-9]*\n(.*?)\n```", re.DOTALL)
count = 0
for name, body in pattern.findall(text):
    if name == "unpack.py":
        continue
    (HERE / name).write_text(body + "\n", encoding="utf-8")
    count += 1
    print("wrote", name)
print(f"unpacked {count} files into {HERE}")
