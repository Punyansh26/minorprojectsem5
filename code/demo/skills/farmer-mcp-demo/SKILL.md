---
name: farmer-mcp-demo
description: Extend this repository's Streamlit farmer-shopping demo, Groq tool routing, or MCP shopping tools while preserving its local-language and transactional boundaries.
---

# Farmer MCP demo development

Read `../../AGENTS.md` and `../../README.md` relative to this skill directory.
Use Conda `minor`; this demo uses Groq for routing, local JSON for state, and
reuses the research STT/VITS models (user decision 2026-09-06). Keep work inside `code/demo`.

The runtime boundary is `app.py` → `assistant.py` / `mcp_client.py` → stdio
`mcp_server.py` → `shop.py`. Manual shopping controls also use MCP. Do not replace
the actual MCP hop with direct function calls while describing the result as MCP.

When adding a shopping capability, implement deterministic facts in `shop.py`,
expose a typed MCP schema, add a grounded template in `responses.py`, then connect
the UI/interpreter. Identity, confirmation capability, and idempotency belong to
the host, not model arguments. Avoid broadening the demo into payments or diagnosis.

Catalogue values are synthetic. Sellable unit counts are distinct from package
weight and field area. Reject unverified application rates. Preserve multilingual
aliases, ambiguity responses, integer money, transactional stock, session ownership,
retry deduplication, and preview-bound checkout confirmation.

Chhattisgarhi templates are drafts. Local MMS uses the configured hne adapter;
VITS uses the notebook checkpoints. Do not claim native speech accuracy, barge-in,
or fully offline conversation: Groq routing still needs internet. Record measured changes and limitations in
`../../../../idea/conversations/` relative to this skill directory.
