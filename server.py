import os
import sys
import asyncio
import base64
import json
import numpy as np
import functools
from google import genai
from google.genai import types
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
import torch

# Audio utils
from audio_utils import bytes_to_float32, float32_to_bytes, resample_audio, is_silence

load_dotenv()

# Setup paths for custom local models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'STT', 'stt-service')))

from src.asr import ChhattisgarhiMMSEngine

try:
    from TTS.utils.synthesizer import Synthesizer
except ImportError:
    print("TTS package not found. Please ensure 'pip install TTS' succeeded.")
    Synthesizer = None

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key or api_key == "your_gemini_api_key_here":
    print("WARNING: GEMINI_API_KEY not set properly in .env")
client = None
if api_key and api_key != "your_gemini_api_key_here":
    client = genai.Client(api_key=api_key)

print("Loading Models... This will take some time.")
stt_engine = None
try:
    stt_engine = ChhattisgarhiMMSEngine()
    print(f"STT Model Loaded on: {stt_engine._device.upper()}")
except Exception as e:
    print(f"Error loading STT Model: {e}")

tts_engine = None
try:
    if Synthesizer:
        use_gpu = torch.cuda.is_available()
        print(f"Initializing TTS... (GPU Enabled: {use_gpu})")
        tts_engine = Synthesizer(
            tts_checkpoint="TTS/Female/best_model.pth",
            tts_config_path="TTS/Female/config.json",
            use_cuda=use_gpu
        )
        print("TTS Model Loaded.")
except Exception as e:
    print(f"Error loading TTS Model: {e}")

print("Server starting...")

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok"}

async def process_voice_turn(audio_buffer: bytes, websocket: WebSocket):
    if not stt_engine or not tts_engine:
        print("Models not loaded properly. Cannot process turn.")
        return

    try:
        print(f"Processing turn with {len(audio_buffer)} bytes of audio.")
        # 1. Convert to float32
        audio_float = bytes_to_float32(audio_buffer)
        
        # 2. Resample from 8kHz to 16kHz for STT
        audio_16k = resample_audio(audio_float, 8000, 16000)
        
        # 3. STT
        print("Running STT...")
        loop = asyncio.get_running_loop()
        stt_result = await loop.run_in_executor(None, functools.partial(stt_engine.transcribe, audio_16k, fast=False))
        text = stt_result.text
        print(f"User Transcribed: {text}")
        
        if not text or not text.strip():
            print("No speech detected.")
            return
            
        # 4. LLM (Gemini)
        print("Calling Gemini...")
        if client:
            def _call_gemini(t):
                return client.models.generate_content(
                    model='gemini-3.5-flash',
                    contents=t,
                    config=types.GenerateContentConfig(
                        system_instruction="You are a friendly voice assistant. You must respond strictly in the Chhattisgarhi language. Keep responses short and conversational, maximum 2 sentences."
                    )
                )
            response = await loop.run_in_executor(None, _call_gemini, text)
            reply_text = response.text
            print(f"Gemini Response: {reply_text}")
        else:
            print("Gemini Client not initialized.")
            reply_text = "Sorry, my brain is offline right now."
        
        # 5. TTS
        print("Running TTS...")
        wav_out = await loop.run_in_executor(None, tts_engine.tts, reply_text)
        wav_out_np = np.array(wav_out, dtype=np.float32)
        
        # 6. Resample TTS to 8kHz for Exotel (assuming Synthesizer outputs 22050Hz)
        wav_8k = resample_audio(wav_out_np, 22050, 8000)
        
        # 7. Convert to 16-bit PCM
        pcm_bytes = float32_to_bytes(wav_8k)
        
        # 8. Send to WebSocket in chunks
        chunk_size = 3200
        for i in range(0, len(pcm_bytes), chunk_size):
            chunk = pcm_bytes[i:i+chunk_size]
            if len(chunk) % 320 != 0:
                padding = 320 - (len(chunk) % 320)
                chunk += b'\x00' * padding
                
            encoded = base64.b64encode(chunk).decode('utf-8')
            await websocket.send_json({"event": "media", "media": {"payload": encoded}})
            await asyncio.sleep(0.2)
            
        print("Finished sending TTS audio.")
        # Send clear to tell Exotel we are done speaking
        await websocket.send_json({"event": "clear"})

    except Exception as e:
        print(f"Error in processing turn: {e}")

@app.websocket("/media")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection accepted.")
    
    audio_buffer = bytearray()
    silence_frames = 0
    is_speaking = False
    
    # Exotel sends chunks around 100ms. 
    # Let's say 15 frames (~1.5s) of silence means the user stopped speaking.
    SILENCE_THRESHOLD_FRAMES = 15 

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            event = msg.get("event")
            
            if event == "connected":
                print("Exotel connected.")
            elif event == "start":
                print("Stream started. Listening for user...")
                audio_buffer.clear()
            elif event == "media":
                payload = msg.get("media", {}).get("payload")
                if payload:
                    chunk = base64.b64decode(payload)
                    
                    if is_silence(chunk, threshold=0.015):
                        silence_frames += 1
                    else:
                        silence_frames = 0
                        is_speaking = True
                    
                    if is_speaking:
                        audio_buffer.extend(chunk)
                    
                    # If we were speaking and now we've had enough silence, process the turn
                    if is_speaking and silence_frames > SILENCE_THRESHOLD_FRAMES:
                        print("Silence detected, processing turn...")
                        # Make a copy of the buffer and clear it
                        turn_audio = bytes(audio_buffer)
                        audio_buffer.clear()
                        is_speaking = False
                        silence_frames = 0
                        
                        # Process in background task so we keep receiving messages
                        asyncio.create_task(process_voice_turn(turn_audio, websocket))

            elif event == "stop" or event == "closed":
                print("Stream stopped by Exotel.")
                break

    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("Connection closed handler.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
