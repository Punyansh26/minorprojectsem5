"""Verify reduced precision is selected before GPU allocation and inputs keep valid dtypes."""

import sys
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from config import STT_ROOT


@pytest.mark.parametrize("device,expected_dtype", [("cuda", "float16"), ("cpu", "float32")])
def test_mms_precision_and_input_types(monkeypatch, device, expected_dtype):
    import torch
    import transformers
    if str(STT_ROOT) not in sys.path:
        sys.path.insert(0, str(STT_ROOT))
    from src import asr
    events = []

    class Input:
        def __init__(self, floating):
            self.floating = floating
        def is_floating_point(self):
            return self.floating
        def to(self, *args, **kwargs):
            events.append(("input", self.floating, args, kwargs))
            return self

    class Processor:
        tokenizer = SimpleNamespace(set_target_lang=lambda lang: events.append(("language", lang)))
        def __call__(self, *args, **kwargs):
            return {"input_values": Input(True), "attention_mask": Input(False)}
        def decode(self, ids):
            return "धान बीज"

    class Model:
        def load_adapter(self, lang):
            events.append(("adapter", lang))
        def to(self, target):
            events.append(("device", target))
            return self
        def eval(self):
            events.append(("eval",))
            return self
        def __call__(self, **kwargs):
            assert not torch.is_grad_enabled()
            return SimpleNamespace(logits=torch.tensor([[[0., 1.]]]))

    def load_model(*args, **kwargs):
        events.append(("load", kwargs["torch_dtype"]))
        return Model()

    monkeypatch.setattr(torch.cuda, "is_available", lambda: device == "cuda")
    monkeypatch.setattr(asr, "settings", replace(asr.settings, ASR_DEVICE=device, MMS_DTYPE="float16"))
    monkeypatch.setattr(transformers.AutoProcessor, "from_pretrained", lambda *a, **kw: Processor())
    monkeypatch.setattr(transformers.Wav2Vec2ForCTC, "from_pretrained", load_model)
    engine = asr.ChhattisgarhiMMSEngine()
    assert engine.transcribe(np.zeros(16000, dtype=np.float32), fast=False).text == "धान बीज"
    dtype = getattr(torch, expected_dtype)
    assert events.index(("load", dtype)) < events.index(("device", device))
    assert ("input", True, (), {"device": device, "dtype": dtype}) in events
    assert ("input", False, (device,), {}) in events
    assert ("eval",) in events
