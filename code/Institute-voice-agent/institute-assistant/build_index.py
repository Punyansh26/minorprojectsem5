"""Maintain the legacy index only; verified releases use kb_pipeline.py."""
from pathlib import Path

from assistant.config import settings
from assistant.kb.common import active_release
from assistant.ingest import build_index

if __name__ == "__main__":
    if active_release(Path(settings.KB_STATE_DIR)):
        raise SystemExit("A verified KB release is active. Use kb_pipeline.py refresh, extract, build, evaluate and activate; see README.md.")
    build_index()
