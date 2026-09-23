"""Run explicit local/provider checks; never create staff tickets or reminders."""
import argparse
import io
import json
from pathlib import Path
from uuid import uuid4

import soundfile as sf

import agent_bridge
import settings as cfg
import speech


def main():
    """Verify real components independently so network failures remain distinguishable."""
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=["tts", "stt", "mms", "online", "hinglish", "agent", "pipeline"])
    parser.add_argument("--provider", choices=["ollama", "groq"], help="Override the configured reasoning provider")
    args = parser.parse_args()
    cfg.configure_agent()
    output = cfg.DATA_ROOT / "smoke"
    output.mkdir(parents=True, exist_ok=True)
    if args.check == "tts":
        for voice in cfg.VOICES:
            result = speech.make_audio("नमस्ते। मैं आपकी मदद के लिए तैयार हूँ।", "hindi", voice)
            (output / f"{voice}.wav").write_bytes(result["data"])
            info = sf.info(io.BytesIO(result["data"]))
            print(voice, info.samplerate, round(info.duration, 2), "seconds", flush=True)
    elif args.check in {"online", "hinglish"}:
        language = "english" if args.check == "online" else "hinglish"
        text = "How can I help with institute admissions?" if language == "english" else "Aap hostel aur admission ke baare mein pooch sakte hain."
        result = speech.make_audio(text, language, "Female", provider=args.provider)
        (output / f"{language}.mp3").write_bytes(result["data"])
        print(language, len(result["data"]), "audio bytes", flush=True)
    elif args.check in {"stt", "mms"}:
        data = (output / "Female.wav").read_bytes()
        text = speech.transcribe(data, "Hindi" if args.check == "stt" else "Chhattisgarhi (experimental)")
        if not text:
            raise RuntimeError("No transcript produced")
        print("Transcript:", text, flush=True)
    else:
        question = "बी टेक में प्रवेश किस आधार पर होता है?"
        if args.check == "pipeline":
            question_audio = speech.make_audio(question, "hindi", "Female")
            question = speech.transcribe(question_audio["data"], "Hindi")
            if not question:
                raise RuntimeError("No transcript produced")
        result = agent_bridge.ask(question, str(uuid4()), {}, provider=args.provider)
        print("Agent status:", result["response_status"], "sources:", len(result.get("sources") or []), flush=True)
        # Only the fixed public smoke question/answer is written, never user conversations.
        (output / f"{args.check}.json").write_text(json.dumps({"question": question, **result}, ensure_ascii=False, indent=2))
        if result["response_status"] != "answered" or not result.get("sources"):
            raise RuntimeError("Live question did not produce a grounded answer; inspect the smoke result")
        print(result["answer_text"], flush=True)
        if args.check == "pipeline":
            audio = speech.make_audio(result["answer_text"], result["language"], "Female", provider=args.provider)
            (output / "pipeline.wav").write_bytes(audio["data"])
            print("Pipeline audio:", len(audio["data"]), "bytes", flush=True)


if __name__ == "__main__":
    main()
