import torch
from TTS.utils.synthesizer import Synthesizer

MODEL = "Female/best_model.pth"
CONFIG = "Female/config.json"
device = torch.cuda.is_available()

tts = Synthesizer(
    tts_checkpoint=MODEL,
    tts_config_path=CONFIG,
    use_cuda=device
)

text = "जम्मू कश्मीर"

wav_default = tts.tts(text=text)
print("Default length:", len(wav_default))

wav_speed = tts.tts(text=text, speed=1.5)
print("Speed 1.5 length:", len(wav_speed))

wav_length = tts.tts(text=text, length_scale=1.5)
print("Length_scale 1.5 length:", len(wav_length))

