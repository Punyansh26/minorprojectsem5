# Demo 2 knowledge-base guide

## Already installed

The rebuilt database is active on this workspace. **Start Demo 2 with `bash run.sh`; do
not run `python build_index.py` to use it.** The legacy builder is blocked while a verified
release is active. Rebuild only when intentionally changing the source corpus or pipeline.

As of 22 September 2026, release `20260922T095421217856Z` contains 222 vector chunks and
613 structured records: 611 JoSAA cutoff rows and two scholarship/finance records. It uses
local `intfloat/multilingual-e5-small` embeddings with BM25 search and exact SQLite rank
lookups. Demo 2 and the text CLI share this release; their conversation/ticket databases
remain separate.

## Where the files live

Paths below are relative to `code/Institute-voice-agent/institute-assistant/`:

| Path | Purpose |
| --- | --- |
| `knowledge_base/` | Supplied PDF and UTF-8 text source documents; folder READMEs are not indexed |
| `kb_sources.json` | Source registry: URLs/local paths, titles, periods and review status |
| `kb_state/raw/` | Cached original bytes, identified by SHA-256 |
| `kb_state/assets/` | Rendered pages and table/figure crops for review |
| `kb_state/reviews.json` | Approvals/corrections tied to source hashes, reviewer and date |
| `kb_state/manual_records.json` | Curated scholarship/finance records with supporting evidence |
| `kb_state/models/` | Local embedding model and Hindi OCR data |
| `kb_state/releases/<release>/chroma/` | Versioned vector database |
| `kb_state/releases/<release>/facts.sqlite` | Matching structured fact database |
| `kb_state/releases/<release>/release.json` | Build status, model profile and counts |
| `kb_state/releases/<release>/validation.json` | Saved retrieval evaluation for that release |
| `kb_state/active.json` | Selects the release served to both applications |
| `kb_state/latest_build.json` | Most recently completed build; it may differ from the active release |
| `kb_state/previous.json` | Previous release or legacy configuration for rollback |
| `chroma_index/` | Original MiniLM index retained for rollback |
| `kb_state/backups/legacy-before-verified-20260922/` | Backup made before activation |

`KB_STATE_DIR` defaults beside the resolved `KB_DIR`. If overriding it, use the same
absolute directory for Demo 2 and the CLI. The installed release manifest also records an
absolute model path; relocation needs a checked configuration and rebuild rather than an
assumption that copied runtime directories are portable.

## Check the active release

This reads metadata and checks that both databases exist. It does not call Groq, load
embedding models or rebuild anything. Run from the shared agent directory:

```bash
conda activate minor
cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant"
python - <<'PY'
from pathlib import Path
from assistant.config import settings
from assistant.kb.common import active_release

active = active_release(Path(settings.KB_STATE_DIR))
if active is None:
    raise SystemExit("No verified release selected; inspect setup before rebuilding.")
root, manifest = active
assert (root / "chroma/chroma.sqlite3").is_file(), "Vector database missing"
assert (root / "facts.sqlite").is_file(), "Structured database missing"
print("Active release:", root.name)
print("Build status:", manifest["status"])
print("Vector chunks:", manifest["chunks"])
print("Cutoff records:", manifest["cutoff_records"])
PY
```

To inspect actual retrieval without the LLM, run `python ask_kb.py` from that directory.
It loads the active local embedding model. Try a fully specified cutoff query or a calendar
question; an empty result is expected for an unavailable quota-specific cutoff.

## Add documents or refresh official sources

Use the existing `minor` environment and run all maintenance commands from the shared
agent directory shown above. `kb_pipeline.py` is not located in `demo2/`.

1. Put public, approved PDF or UTF-8 `.txt` source documents in the appropriate
   `knowledge_base/` subfolder. Add their relative paths and metadata under `local_sources`
   in `kb_sources.json`. Register web sources under `sources`. Record the actual effective
   period; a filename or download date alone does not establish that a policy is current.
2. Register/fetch sources and extract evidence:

   ```bash
   python kb_pipeline.py refresh --discover
   # Use this when refreshing the official cutoff dataset:
   python kb_pipeline.py ranks --years 2026 2025 2024 2023 2022
   python kb_pipeline.py extract
   python kb_pipeline.py report
   ```

   `refresh --only-new` still registers local files but skips already-known remote URLs.
   It will not retry an existing failed URL; use a normal refresh for that. Refresh is
   bounded and stores failures. It does not guarantee that the institute site is reachable.
3. Inspect the [source inventory](../Institute-voice-agent/institute-assistant/docs/KB_SOURCE_INVENTORY.md),
   [extraction review queue](../Institute-voice-agent/institute-assistant/docs/KB_EXTRACTION_REVIEW.md),
   original documents and saved crops. Approve only verified evidence. OCR, chart labels,
   fee amounts, deadlines, rank definitions and eligibility conditions need particular care.
4. Store block approvals/corrections in `kb_state/reviews.json`, keyed by block ID, with
   `source_sha256`, `reviewer`, `reviewed_at` and `status: "approved"`. Correct `text`,
   `rows`, `years` or `period` where necessary. A changed source hash invalidates the old
   block approval. Re-run `python kb_pipeline.py extract` after review.
5. Build and evaluate a candidate release:

   ```bash
   python kb_pipeline.py build
   python kb_pipeline.py evaluate
   ```

   `build` writes a new release and reports its ID. `evaluate` defaults to the latest build;
   use `--release ID` to select a particular one. Add `--baseline` only when the original
   index is available and you want the legacy comparison. Inspect the printed `passed`
   field and saved validation; completing the command alone is not a passing result.
6. Review live answers separately when the provider is available:

   ```bash
   python evaluate_helpdesk.py --live --provider ollama --release RELEASE_ID \
     --case verified_cutoff --case cg_scholarship --case loan_conditions \
     --case loan_institute_eligibility --case spot_current \
     --output /tmp/demo2-candidate-live.json
   ```

   Replace `RELEASE_ID` with the candidate ID. This tests the staged release without
   switching the app and blocks ticket/reminder writes. Inspect answers and quotations,
   not only their status. Rate-limited calls remain unavailable and do not validate answers.
   Ollama is the default; prepare it using the
   [local inference guide](../Institute-voice-agent/institute-assistant/docs/LOCAL_INFERENCE.md).
   For an explicit cloud check, use `--provider groq --interval 30` and a configured key.
7. Publish the selected candidate after checking its evidence and evaluation:

   ```bash
   python kb_pipeline.py activate --release RELEASE_ID
   python kb_pipeline.py report
   ```

Activation requires a complete build and passing retrieval gate: at least 90 cases,
at least 90% supporting-evidence recall, and all exact-cutoff checks passing. The gate
does not automatically establish live answer correctness. The active pointer switches
both stores together; the next retrieval uses the selected release.

Moving or deleting a source PDF alone does not retire its cached evidence. Source
retirement and supersession require reviewing the registry and retained source inventory,
then re-extracting, rebuilding and verifying that the superseded material is excluded.
Do not delete files inside an active release to change its answers.

## Roll back

From the shared agent directory:

```bash
python kb_pipeline.py rollback
```

This restores the previously recorded release, or the original index after the first
activation. Keep the previous release and legacy files intact. A build or failed refresh
does not switch the active database. Restart Demo 2 after changing code or environment
variables; a normal release-pointer change is followed automatically by retrieval.

## Fresh checkout or another machine

The ready-to-use database exists on this workspace. Large raw files, models, assets and
release databases are ignored by Git; a clone alone does not contain them. Preserve the
review records and source registry, obtain the required source documents, and follow the
review/build/evaluate/activate workflow on the destination machine.

`python kb_pipeline.py bootstrap` downloads the pinned embedding model and Hindi OCR
data. Run it only when those artifacts are missing. Tesseract with English language data
must also be installed. Preserve the shared speech dependency versions when installing
missing packages. See the [agent setup and maintenance documentation](../Institute-voice-agent/institute-assistant/README.md)
for configuration and dependencies.

## Coverage and remaining gaps

The corpus includes JoSAA All India cutoff rows for 2022–2026, supplied institute documents,
the CG post-matric scholarship notice and PM-Vidyalaxmi rules. Every rank keeps its year,
authority, round, programme, quota, category, seat pool and rank basis. General financial
rules retain their eligibility qualifications and do not confirm current IIIT-NR inclusion.

Current institute spot notices, CG/NTPC and CSAB cutoffs, college-funded aid, bank-specific
rates and several hostel/service policies remain unverified. During the recorded audit,
26 source fetches failed and 267 extraction blocks still needed review. Use the
[46-question offline checklist](OFFLINE_INFORMATION_NEEDED.md) to collect evidence;
the checklist itself is not indexed as policy.

For dated measurements and live-provider limits, see [VALIDATION.md](VALIDATION.md).
