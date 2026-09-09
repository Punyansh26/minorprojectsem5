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

text = "जम्मू कश्मीर म पर्यटन उद्योग ला बढ़ावा देना उहाँ के अर्थबेवस्था ला सुचारू रूप ले चलाय बर जरुरी हे"

# Default length
wav_default = tts.tts(text=text)
print("Default length:", len(wav_default))

# Change speed directly on the underlying model
tts.tts_model.length_scale = 1.5
wav_slower = tts.tts(text=text)
print("Slower (length_scale=1.5) length:", len(wav_slower))

tts.tts_model.length_scale = 0.5
wav_faster = tts.tts(text=text)
print("Faster (length_scale=0.5) length:", len(wav_faster))

