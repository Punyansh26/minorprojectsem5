# hostel

Hostel allotment policy, room-sharing rules, hostel handbook/rules.

The rebuilt knowledge base is already active and shared with Demo 2. No rebuild is needed
to use the existing release. This folder holds source documents; the active vector index
and structured facts are stored under `kb_state/releases/`, selected by `kb_state/active.json`.

To add hostel information, place approved public PDF or UTF-8 `.txt` documents here and
register their source details in `kb_sources.json`. Follow the
[knowledge-base maintenance workflow](../../README.md#maintain-the-knowledge-base):
`kb_pipeline.py refresh`, `extract`, review the evidence, `build`, `evaluate`, then `activate`.
Run these commands from the `institute-assistant` directory in the `minor` environment.

`python build_index.py` is the legacy command and refuses to run while a verified release
is active. This README is guidance, not indexed hostel-policy evidence.
