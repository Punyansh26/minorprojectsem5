---
name: demo-verification
description: Test or rehearse this repository's farmer-shopping Streamlit MCP demo, separating real protocol checks from live Groq and speech-provider checks.
---

# Demo verification

Use Conda `minor` and run commands from `code/demo`. Read `../../README.md` for
the presentation script. `python -m pytest -q` exercises JSON invariants, actual
MCP subprocess transport, model doubles, audio validation, and Streamlit controls.
`python -m pip check` must stay clean because minor also contains the research stack.

For protocol changes, test server initialization, tool discovery, schema rejection,
actual cart mutation, replay, and host-only checkout confirmation. A mocked tool
result or a domain-only test is not evidence that MCP transport works.

Live checks use `python smoke_demo.py --live` with a configured Groq key; the
default smoke check is keyless and uses a temporary JSON store. Use synthetic text
and synthesized speech for provider checks, not participant recordings.

In the UI, rehearse search → two packs → cart → checkout preview → confirmation;
also check out-of-stock, unknown item, ambiguous organic manure, and a dosage
referral. Verify automatic submission and visible transcript/reply and playable reply audio.

Report actual test results separately from untested microphone/browser behavior,
native-speaker quality, and live provider availability. Save useful results in
the project's `idea/conversations` folder without keys or raw recordings.
