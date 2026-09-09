import math
import struct
import wave

def generate_beep_sequence(filename, duration_seconds=10, sample_rate=8000):
    print(f"Generating {duration_seconds} seconds of test audio to {filename}...")
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        # 440 Hz (A4)
        frequency = 440.0
        
        for i in range(int(sample_rate * duration_seconds)):
            # Beep for 0.5s, silence for 0.5s
            if (i // (sample_rate // 2)) % 2 == 0:
                value = int(32767.0 * math.sin(frequency * math.pi * 2 * i / sample_rate) * 0.5) # 0.5 volume
            else:
                value = 0
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)
    print("Done!")

if __name__ == "__main__":
    generate_beep_sequence('test_audio.wav')
