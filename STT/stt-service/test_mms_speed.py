import sys, time
sys.path.insert(0, ".")
import numpy as np
from src.asr import ChhattisgarhiMMSEngine

print("Loading MMS model (this alone can take a minute)...")
engine = ChhattisgarhiMMSEngine()

# 5 seconds of silence as a rough timing proxy (real speech will be similar cost)
audio = np.zeros(16000 * 5, dtype=np.float32)

t0 = time.monotonic()
result = engine.transcribe(audio, fast=False)
print(f"Inference time: {result.inference_ms:.0f} ms for 5s of audio")