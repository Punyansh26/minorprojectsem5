# general

Campus facilities, local area info, anything not covered by the other categories.

The rebuilt database is already active for Demo 2. This folder holds source documents;
no indexing command is needed to start the app.

To add information, place public PDF or UTF-8 `.txt` documents here, register their metadata
in `kb_sources.json`, and follow the
[knowledge-base maintenance workflow](../../README.md#maintain-the-knowledge-base):
refresh, extract, review, build, evaluate and activate with `kb_pipeline.py` from the
`institute-assistant` directory in the existing `minor` environment.

`python build_index.py` is the legacy command and refuses to run while a verified release
is active. Folder READMEs are guidance and are not indexed as factual evidence.
