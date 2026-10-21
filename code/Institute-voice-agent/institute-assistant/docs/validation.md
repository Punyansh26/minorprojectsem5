# Helpdesk validation — 2026-09-18

This is a historical Groq run against the earlier index. For the current Ollama default,
159 passing automated tests and final Hindi voice check, see
[local model validation](LOCAL_MODEL_VALIDATION.md) and [Demo 2 validation](../../../demo2/VALIDATION.md).

Environment: existing `minor` Conda environment and the configured Groq model
(`openai/gpt-oss-120b`), with the existing local institute PDF index.

- `python -m pytest -q`: 36 passed. Chroma emitted existing Pydantic deprecation warnings;
  no telemetry capture errors. Tests made no external API or email calls.
- CLI smoke: invalid email rejection, `gen` normalization, English and Hindi greetings,
  fresh conversation with `/new`, and clean exit passed using a temporary checkpoint DB.
- Targeted live evaluation: 5/5 status/language checks passed. Cases cover English, Hindi,
  Hinglish, a contextual CG-quota follow-up, and an unsupported 2027 hostel laundry price.
  Answers and exact source quotes are in [helpdesk-evaluation.json](helpdesk-evaluation.json).
- The whale example and an instruction-override/prompt-disclosure request were also
  redirected during live testing. They reached no retrieval or action creation.
- `git diff --check` and Python compilation completed without errors.

The live evaluation used memory-only sessions and blocked all ticket/reminder writes.
The JSON `seconds` field includes deliberate 40-second pauses per turn for provider quotas;
it is not a response-latency benchmark. No SMTP messages were sent. The existing `.env`,
student databases, and source PDFs were preserved.

These checks establish behavior on this small sample, not production accuracy. Exact source
quotes validate provenance; model review can still miss a mistranslation or qualification.
The CG reply still includes more eligibility detail than the narrow question requires, and
its date wording needs clearer 'on or after' phrasing. Review that output with college staff
before using it as a reference answer. Expand evaluation to fees, refunds, hostel rules,
deadlines, conflicting documents, ambiguous speech transcripts, and real call traffic before
public deployment. Chhattisgarhi has not been validated.
