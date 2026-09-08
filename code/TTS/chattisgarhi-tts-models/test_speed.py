import torch
from TTS.utils.synthesizer import Synthesizer
import time

MODEL = "Female/best_model.pth"
CONFIG = "Female/config.json"
device = torch.cuda.is_available()

tts = Synthesizer(
    tts_checkpoint=MODEL,
    tts_config_path=CONFIG,
    use_cuda=device
)

text = "जम्मू कश्मीर"

try:
    wav1 = tts.tts(text=text, speed=1.5)
    print("speed works")
except Exception as e:
    print(f"speed error: {e}")

try:
    wav2 = tts.tts(text=text, length_scale=1.5)
    print("length_scale works")
except Exception as e:
    print(f"length_scale error: {e}")

