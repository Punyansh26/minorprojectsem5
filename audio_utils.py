import numpy as np
from scipy import signal

def bytes_to_float32(audio_bytes):
    """Convert 16-bit PCM bytes to float32 numpy array (-1.0 to 1.0)"""
    data = np.frombuffer(audio_bytes, dtype=np.int16)
    return data.astype(np.float32) / 32768.0

def float32_to_bytes(audio_array):
    """Convert float32 numpy array to 16-bit PCM bytes"""
    audio_array = np.clip(audio_array, -1.0, 1.0)
    data = (audio_array * 32767.0).astype(np.int16)
    return data.tobytes()

def resample_audio(audio_array, orig_sr, target_sr):
    """Resample an audio array"""
    if orig_sr == target_sr:
        return audio_array
    
    num_samples = int(round(len(audio_array) * float(target_sr) / orig_sr))
    return signal.resample(audio_array, num_samples)

def is_silence(audio_bytes, threshold=0.02):
    """Calculate RMS energy of 16-bit PCM audio to detect silence"""
    data = np.frombuffer(audio_bytes, dtype=np.int16)
    if len(data) == 0:
        return True
    
    rms = np.sqrt(np.mean(np.square(data.astype(np.float32) / 32768.0)))
    return rms < threshold
