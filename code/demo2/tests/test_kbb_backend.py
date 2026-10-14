"""Demo 2 follows the kbb release by default and can fall back to the legacy store with one variable."""
import os

import pytest

import health
import settings


@pytest.fixture
def clean_env(monkeypatch):
    for key in ("KB_BACKEND", "KB_STATE_DIR", "KBB_ROOT", "DEMO2_KB_BACKEND", "DEMO2_KBB_STATE_DIR"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_configure_agent_defaults_to_kbb(clean_env, tmp_path):
    clean_env.setattr(settings, "DATA_ROOT", tmp_path)
    settings.configure_agent()
    assert os.environ["KB_BACKEND"] == "kbb"
    assert os.environ["KB_STATE_DIR"] == str(settings.KBB_ROOT / "data/kbb/serving")
    assert os.environ["KBB_ROOT"] == str(settings.KBB_ROOT)


def test_legacy_backend_leaves_state_dir_to_the_agent(clean_env, tmp_path):
    clean_env.setattr(settings, "DATA_ROOT", tmp_path)
    clean_env.setenv("DEMO2_KB_BACKEND", "legacy")
    settings.configure_agent()
    assert os.environ["KB_BACKEND"] == "legacy"
    assert "KBB_ROOT" not in os.environ


def test_unknown_backend_is_rejected(clean_env, tmp_path):
    clean_env.setattr(settings, "DATA_ROOT", tmp_path)
    clean_env.setenv("DEMO2_KB_BACKEND", "chroma")
    with pytest.raises(ValueError):
        settings.configure_agent()


@pytest.mark.skipif(not (settings.KBB_ROOT / "data/kbb/serving/active.json").exists(), reason="no active kbb release")
def test_runtime_health_reports_the_kbb_release(clean_env):
    settings.configure_agent()
    sys_path = str(settings.AGENT_ROOT)
    import sys
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from assistant.config import settings as agent_settings        # frozen singleton: pin the state dir explicitly
    original = agent_settings.KB_STATE_DIR
    object.__setattr__(agent_settings, "KB_STATE_DIR", os.environ["KB_STATE_DIR"])
    try:
        result = health.runtime_health()
    finally:
        object.__setattr__(agent_settings, "KB_STATE_DIR", original)
    assert result["engine"] == "kbb" and result["release_ok"] and result["release_integrity"] == "bound"
    assert result["cutoff_records"] == 611
    assert result["pending_critical_reviews"] == 0
    assert "error_code" not in result
