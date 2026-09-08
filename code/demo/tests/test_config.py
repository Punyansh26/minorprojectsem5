"""Keep browser speech configuration independent from the research service's GPU choice."""

import os
import subprocess
import sys


def test_demo_gpu_precision_overrides_research_settings():
    # Import config in isolation so the test cannot change another test's cached settings.
    script = '''
import config
config.STT_ENV["STT_DEVICE"] = "cpu"
config.configure_stt()
import sys
sys.path.insert(0, str(config.STT_ROOT))
from src.config import settings
assert config.STT_DEVICE == "cuda"
assert settings.ASR_DEVICE == "cuda"
assert settings.MMS_DTYPE == "float16"
'''
    env = {**os.environ, "STT_DEVICE": "cpu", "DEMO_STT_DEVICE": "cuda", "DEMO_STT_DTYPE": "float16"}
    subprocess.run([sys.executable, "-c", script], env=env, check=True, timeout=10)
