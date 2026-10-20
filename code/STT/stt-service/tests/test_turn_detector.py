"""
Unit tests for semantic EOU gating (chapter 03 §3.2).

Covers the pure finalisation decision function and the detector's graceful
degradation when no ONNX model is available. No model weights, no network, no
server. Run from the stt-service root:

    conda activate minor
    cd code/STT/stt-service
    python -m pytest tests/test_turn_detector.py -q
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.turn_detector import (
    SemanticTurnDetector,
    EouResult,
    should_finalize,
    EOU_WINDOW_SECONDS,
)
from src.config import settings


# --- should_finalize: legacy (no model) behaviour -------------------------

def test_no_model_reduces_to_silence_cap():
    # eou_p=None => semantic clause false => endpoint at max_silence only.
    assert should_finalize(silence_ms=399, utterance_ms=2000, eou_p=None,
                           min_silence_ms=300, max_silence_ms=400,
                           eou_tau=0.5, max_utterance_ms=20000) is False
    assert should_finalize(silence_ms=400, utterance_ms=2000, eou_p=None,
                           min_silence_ms=300, max_silence_ms=400,
                           eou_tau=0.5, max_utterance_ms=20000) is True


def test_min_silence_floor_blocks_early_cut():
    # Even a very confident model cannot cut before the min-silence floor.
    assert should_finalize(silence_ms=100, utterance_ms=2000, eou_p=0.99,
                           min_silence_ms=300, max_silence_ms=1500,
                           eou_tau=0.5, max_utterance_ms=20000) is False


def test_confident_eou_commits_early():
    # Past the floor, a confident completion finalises before the silence cap.
    assert should_finalize(silence_ms=350, utterance_ms=2000, eou_p=0.8,
                           min_silence_ms=300, max_silence_ms=1500,
                           eou_tau=0.5, max_utterance_ms=20000) is True


def test_low_confidence_waits_for_cap():
    # Below tau, we keep waiting until the safety cap (avoids false cut).
    assert should_finalize(silence_ms=800, utterance_ms=2000, eou_p=0.2,
                           min_silence_ms=300, max_silence_ms=1500,
                           eou_tau=0.5, max_utterance_ms=20000) is False
    assert should_finalize(silence_ms=1500, utterance_ms=2000, eou_p=0.2,
                           min_silence_ms=300, max_silence_ms=1500,
                           eou_tau=0.5, max_utterance_ms=20000) is True


def test_max_utterance_always_finalises():
    # The hard length cap wins regardless of silence/EOU.
    assert should_finalize(silence_ms=0, utterance_ms=20000, eou_p=None,
                           min_silence_ms=300, max_silence_ms=1500,
                           eou_tau=0.5, max_utterance_ms=20000) is True


def test_threshold_boundary_is_inclusive():
    assert should_finalize(silence_ms=350, utterance_ms=2000, eou_p=0.5,
                           min_silence_ms=300, max_silence_ms=1500,
                           eou_tau=0.5, max_utterance_ms=20000) is True


# --- detector graceful degradation ----------------------------------------

def test_detector_disabled_by_default():
    d = SemanticTurnDetector()
    # With EOU disabled in config, predict() returns no opinion, never raises.
    res = d.predict(np.zeros(16000, dtype=np.float32))
    assert isinstance(res, EouResult)
    assert res.available is False
    assert res.p_complete is None


def test_detector_missing_file_degrades(monkeypatch):
    # Enable EOU but point at a non-existent file: must degrade, not raise.
    import dataclasses
    import src.turn_detector as td
    patched = dataclasses.replace(td.settings, EOU_ENABLED=True,
                                  EOU_MODEL_PATH="/nonexistent/eou-model.onnx")
    monkeypatch.setattr(td, "settings", patched)
    d = SemanticTurnDetector()
    res = d.predict(np.zeros(16000, dtype=np.float32))
    assert res.available is False
    assert res.p_complete is None
    assert "not found" in res.reason.lower()


# --- input preparation contract -------------------------------------------

def test_input_padding_shape_and_left_pad():
    d = SemanticTurnDetector()
    target = int(EOU_WINDOW_SECONDS * settings.SAMPLE_RATE)
    short = np.ones(1000, dtype=np.float32)
    x = d._prepare_input(short)
    assert x.shape == (1, target)
    # Left-padded with zeros, real samples at the end.
    assert x[0, 0] == 0.0
    assert x[0, -1] == 1.0
    assert int((x[0] != 0).sum()) == 1000


def test_input_truncates_to_last_window():
    d = SemanticTurnDetector()
    target = int(EOU_WINDOW_SECONDS * settings.SAMPLE_RATE)
    long = np.arange(target + 5000, dtype=np.float32)
    x = d._prepare_input(long)
    assert x.shape == (1, target)
    # Keeps the LAST `target` samples.
    assert x[0, -1] == float(target + 5000 - 1)


def test_probability_coercion_sigmoid_and_passthrough():
    # Already-sigmoided value passes through; a logit gets a sigmoid.
    assert SemanticTurnDetector._to_probability(np.array([0.73])) == 0.73
    logit = SemanticTurnDetector._to_probability(np.array([2.0]))
    assert 0.8 < logit < 0.9  # sigmoid(2.0) ~= 0.88
