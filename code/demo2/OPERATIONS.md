# Local operation and recovery

This is a supervised laptop application bound to `127.0.0.1`. Student references,
email addresses and admission categories are self-reported context. They are not
authentication. Do not expose this instance to a LAN or public URL without a separate
HTTPS/authentication/ownership design. No email or reminder is sent by Demo2.

## Start and inspect

Use the existing `minor` environment and `bash run.sh`. Restart after source or package
changes. `python ops.py status` prints actual release integrity, routing configuration
and storage counts, without conversation contents or secrets. Keep `.env` local.
The app and offline write operations share an exclusive `data/runtime.lock`; two
processes cannot safely run against the same four stores.

One reasoning worker serializes graph operations and one worker prepares speech. Queue
capacity is three waiting requests plus executing work. A conversation has at most one
outstanding request, including speech. Excess requests get a busy response before STT
or model work. Queue expiry is 60 seconds, answer deadline 120 seconds from submission,
and speech budget 45 seconds from scheduling, including its queue. Provider timeouts
use the remaining budget. Cancellation checks occur between native/model stages; a
native call cannot be forcibly interrupted safely and keeps its slot until it returns.
Late results/audio are suppressed. Reviewed text is published before speech begins.

`Retry audio` reuses the reviewed answer. It preserves the original reasoning provider
and does not replay the graph. Failed question retries retain original profile/provider
and turn ID. A successful request result survives restart. Draft creation and its
conversation/turn idempotency key commit in one SQLite transaction. Reusing an ID with
different contents fails rather than creating another draft.

## Retention and deletion

Sessions have a fixed 24-hour lifetime. Maintenance runs every five minutes while the
app is running and on startup; active work is allowed to drain before erasure. On a
successful turn, only the newest two complete checkpoints are retained; each carries
the bounded conversation history. Audio and uploaded recordings are not saved by the
runtime. Transient audio/jobs and recording identifiers have finite limits.

New conversation isolates memory and cancels outstanding work. Delete conversation
also removes its checkpoint/write rows, local ticket/reminder drafts, durable results
and owned retrieval/draft cache entries. It removes managed backup bundles, and a
tombstone prevents restoring a deleted conversation from an external copy of an
otherwise valid managed backup. Existing legacy conversations receive one 24-hour
migration grace period; legacy unowned drafts expire by timestamp afterward. Other
users' active conversations survive cleanup.

Cache TTL is one hour, at most 2,000 entries and 64 MiB of serialized payload. SQLite
allocation and WAL overhead are additional; deleting rows makes pages reusable and
does not shrink files immediately. These are logical retention controls, not secure
erasure of SSD blocks, swap, browser downloads or manually copied backups. Backups
outside the managed directory remain the operator's responsibility.

## Backup and restore drill

Stop the app first. The operator command refuses a live runtime's storage lock.

```bash
python ops.py maintain
python ops.py backup
python ops.py restore --backup data/backups/RETURNED_ID --destination /tmp/demo2-recovery
python ops.py status --data /tmp/demo2-recovery
```

Backups use SQLite's online backup API, include SHA-256 checksums and expire after
24 hours. Restore requires an empty destination, valid checksums and SQLite integrity,
then applies current deletion tombstones and expiry. Never overwrite a running store
or copy only a live database's main file while ignoring WAL sidecars. To use a verified
restore, stop the app and set `DEMO2_DATA_DIR` to that recovery directory before restart.
Deletion removes managed backups that could contain the deleted conversation.

## Knowledge maintenance and rollback

Use the sibling `kb_pipeline.py` commands. `source-status SOURCE_ID --owner NAME
--review-by YYYY-MM-DD --reason TEXT [--retire] [--superseded-by ID]` updates lifecycle
metadata for the next build. It never changes the serving release. A failed fetch is
not a new policy verification. Source ownership is still unassigned until staff accept it.

Build a new release, run `evaluate --release ID`, inspect critical answers against the
original pages, then `activate --release ID`. Version 2 manifests bind parents, source
inventory, policies, logical SQLite content, vector files and embedding artifacts.
Activation also binds the validation result. Corruption or mismatch fails closed.
`rollback` restores the preserved previous pointer. Never edit an active release.
The embedding path resolves relative to the KB state root; copy its `models/` directory
with releases when testing a portable restore. The old legacy index is retained.

## Environment and source reproduction

The tested compatibility repair is `compatibility-constraints.txt`. It resolves the
protobuf constraints of Streamlit, audiotools, ONNX Runtime and Chroma's telemetry
dependencies without changing Torch, Transformers, Coqui TTS or trained weights.
`python -m pip check` must pass. Installations must be reviewed against the full
environment inventory in `evaluation/upgrade-20260930/environment-after.json`; this
constraints file alone does not install the entire application.

The temporary clone and original-version rollback wheels are under ignored
`data/upgrade-20260930/`. To roll dependencies back, stop the app and run minor's pip
with `--no-index --find-links data/upgrade-20260930/rollback-wheels -r
data/upgrade-20260930/rollback-requirements.txt`. That intentionally restores the old
declared conflicts, so use it only for diagnosis. Three added pure Python support
packages can remain installed; they do not replace the protected model stack.

The shared agent is a nested Git repository. `.gitmodules` now names the correct
`code/Institute-voice-agent` path. Uncommitted improvements must travel with the source
bundle; checking out the old gitlink alone omits them. The bundle includes a per-file
manifest and excludes credentials, conversations, voices and model binaries. A second
machine still needs the artifact inventory and matching prepared tokenizers/models.
The local clone/restore checks are not a from-scratch second-machine installation.

## Release limits

JEV stays off. Benchmark copies may bypass certificate checks only inside their
isolated evaluation process, with actions blocked. Three full trials, independent
fresh human holdout review and source approval are required for promotion. Synthetic
development examples are never independent gold. Technical extraction review is
separate from institute policy approval.

English/Hinglish speech uses the consumer Edge adapter only after per-session consent;
it has no Azure service guarantee. Hindi VITS, Whisper and cached embeddings run locally.
Check code, model, source-document and voice rights separately before redistribution.
The supplied VITS voice checkpoints do not carry a verified redistribution/voice-consent
attestation in this project. MMS/Chhattisgarhi quality and native speech remain experimental.
