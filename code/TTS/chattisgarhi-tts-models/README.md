# Chhattisgarhi Text-to-Speech (TTS) Models

This repository contains Text-to-Speech (TTS) models for the **Chhattisgarhi** language, powered by [Coqui TTS](https://github.com/coqui-ai/TTS) using the VITS architecture.

## Features

- Synthesizes high-quality speech from Chhattisgarhi text in Devanagari script.
- Includes pre-trained VITS models for both **Male** and **Female** voices.
- Easy to use with the Coqui TTS synthesizer API.

## Directory Structure

- `Female/`: Contains the `best_model.pth` checkpoint and `config.json` for the female voice model.
- `Male/`: Contains the `best_model.pth` checkpoint and `config.json` for the male voice model.
- `indictts.ipynb`: A Jupyter Notebook demonstrating how to load the models and generate speech audio files.

## Prerequisites

To use these models, you will need Python installed along with PyTorch and the Coqui TTS library.

```bash
pip install torch TTS
```

## Usage

You can use the models either via the provided Jupyter Notebook (`indictts.ipynb`) or directly in a Python script. 

Here is a quick example of how to load the model and synthesize text:

```python
import torch
from TTS.utils.synthesizer import Synthesizer

# Select the model and configuration you want to use (Male or Female)
MODEL_PATH = "Female/best_model.pth"
CONFIG_PATH = "Female/config.json"

# Automatically use GPU if available
device = torch.cuda.is_available()

# Initialize the Synthesizer
tts = Synthesizer(
    tts_checkpoint=MODEL_PATH,
    tts_config_path=CONFIG_PATH,
    use_cuda=device
)

# Text to synthesize in Chhattisgarhi (Devanagari script)
text = "मुला तोर संग रहना हे"

# Generate the audio
wav = tts.tts(text=text)

# Save to a file
tts.save_wav(
    wav=wav,
    path="output.wav"
)

print("Audio generated: output.wav")
```

## Hardware Requirements

While the models can run on a CPU, it is highly recommended to run them on a GPU (CUDA) for significantly faster inference speeds.

## License

MIT
