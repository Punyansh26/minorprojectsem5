"""Read actual runtime manifests without loading models or exposing configuration secrets."""
from pathlib import Path
import json
import sys
from datetime import date
from functools import lru_cache

import settings as cfg


@lru_cache(maxsize=8)
def verified_release(root, manifest_hash):
    """Hash immutable content once per manifest, including the prepared embedding model."""
    from assistant.kb.integrity import verify
    root = Path(root)
    manifest = json.loads((root/'release.json').read_text())
    verify(root,manifest,json.loads((root/'validation.json').read_text()))
    return True


def environment_summary():
    import sys
    import platform
    import settings as cfg
    from assistant.config import settings
    try:
        import torch
        torch_version = torch.__version__
    except ImportError:
        torch_version = "missing"
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "torch_version": torch_version,
        "ollama_model": settings.OLLAMA_MODEL,
        "ollama_url": getattr(settings, "OLLAMA_BASE_URL", getattr(settings, "OLLAMA_URL", "http://127.0.0.1:11434")),
        "stt_device": cfg.STT_DEVICE,
        "tts_device": cfg.TTS_DEVICE,
        "speech_threads": cfg.SPEECH_THREADS,
        "whisper_model": cfg.WHISPER_MODEL,
        "data_root": str(cfg.DATA_ROOT)
    }


def dependency_check():
    import importlib.metadata
    deps = ["streamlit", "torch", "faster_whisper", "TTS", "edge_tts", "langchain_chroma", "sentence_transformers", "pdfplumber"]
    result = {}
    for dep in deps:
        try:
            result[dep] = importlib.metadata.version(dep)
        except importlib.metadata.PackageNotFoundError:
            result[dep] = "missing"
    return result


def runtime_health():
    """Inspect the active release and distinguish missing activation from corrupt assets."""
    cfg.configure_agent()
    if str(cfg.AGENT_ROOT) not in sys.path:
        sys.path.insert(0,str(cfg.AGENT_ROOT))
    from assistant.config import settings
    from assistant.kb.common import active_release
    result = {"provider":settings.LLM_PROVIDER, "model":settings.OLLAMA_MODEL,
              "jev_mode":settings.JEV_ROUTING_MODE, "jev_artifact":Path(settings.JEV_ARTIFACT_DIR).name,
              "jev_activation":"not_activated", "release":None,"release_ok":False}
    try:
        active = active_release(Path(settings.KB_STATE_DIR))
        if active:
            root,manifest = active
            if manifest.get('content_sha256'):
                from assistant.kb.integrity import file_hash
                verified_release(str(root),file_hash(root/'release.json'))
            result.update(release=manifest["release"],release_ok=all((root/p).is_file() for p in
                ("facts.sqlite","parents.json","chroma/chroma.sqlite3")),
                release_integrity="legacy_unbound" if not manifest.get("content_sha256") else "bound",
                chunks=manifest.get("chunks"),cutoff_records=manifest.get("cutoff_records"),
                evidence_blocks=manifest.get("evidence_blocks"))
            inventory=json.loads((root/'sources.json').read_text())
            sources=inventory.get('sources',[]) if isinstance(inventory,dict) else inventory
            result['sources_unassigned']=sum(s.get('source_owner','unassigned')=='unassigned' for s in sources)
            result['sources_review_overdue']=sum(bool(s.get('review_by')) and s['review_by']<date.today().isoformat() for s in sources)
        artifact = Path(settings.JEV_ARTIFACT_DIR)
        if (artifact/"activation.json").exists():
            from assistant.jev.runtime import activation_valid,artifact_signature,checked_manifest
            manifest = checked_manifest(str(artifact),artifact_signature(artifact))
            result["jev_activation"] = "activated" if activation_valid(artifact,manifest) else "invalid_activation"
            result["jev_backend"] = manifest.get('backend', 'custom')
        elif not (artifact/"manifest.json").is_file():
            result["jev_activation"] = "artifact_missing"
    except (ValueError,KeyError,TypeError,OSError):
        result["error_code"] = "runtime_integrity_error"
    result["voices"] = {voice:(cfg.TTS_ROOT/voice/"best_model.pth").is_file() for voice in cfg.VOICES}
    result["environment"] = environment_summary()
    result["dependencies"] = dependency_check()
    return result
