"""Neutral acknowledgement cues to cover LLM/tool latency (Task 07 A4 / §7).

A voice turn has two silences for tool/LLM work [R02]: before the first word and while a
tool runs. Playing a cached, *neutral* backchannel immediately after end-of-turn makes the
agent feel responsive even though the grounded answer is still several seconds away.

Design constraints from §7, which this module enforces:

  - Fillers are **neutral only** ("एक पल…" / "one moment…"). They must never imply an answer
    that verification might later reject, and must not be spoken in a way that misleads on
    out-of-scope / insufficient turns. The caller decides *whether* to play a filler; this
    module only provides the neutral audio.
  - Fillers are rendered through the same local VITS path (Hindi) and reuse the Task 07
    pre-synthesised audio cache, so after a one-time build-step render they play with ~0 ms
    synthesis.
  - The cache key binds the KB release and TTS model version like every other entry, so a
    model change regenerates the fillers too.
"""
import speech
import tts_cache

# Neutral, answer-free fillers per language. Hindi uses the local VITS voice; English/Hinglish
# fillers are only available when online speech is enabled (same policy as answers).
FILLERS = {
    "hindi": ["एक पल।", "देख रहा हूँ।"],
    "english": ["One moment.", "Let me check."],
    "hinglish": ["Ek pal.", "Dekh raha hoon."],
}


def filler_text(language: str, index: int = 0) -> str:
    """Return a neutral filler phrase for the language, clamped to the available set."""
    options = FILLERS.get(language)
    if not options:
        raise ValueError("No filler available for this language.")
    return options[index % len(options)]


def filler_audio(language: str, voice: str, speed: float = 1.0, index: int = 0, *,
                 allow_online: bool = False) -> dict:
    """Return rendered neutral-filler audio, served from the pre-synthesised cache on a hit.

    This is always ``cacheable``: fillers are fixed, answer-free phrases, so caching them is
    safe and is the whole point (sub-millisecond replay after the first render / build step).
    """
    text = filler_text(language, index)
    return speech.make_audio(text, language, voice, speed,
                             allow_online=allow_online, cacheable=True)


def prerender(voice: str, speeds=(1.0,), languages=("hindi",)) -> dict:
    """Render and cache every neutral filler for the given voices/speeds/languages.

    Intended for a build-time step (see ``prerender_fillers.py``). Returns a small report of
    what was rendered so the caller can log coverage. Only local (Hindi) fillers render here;
    online languages are skipped unless rendered explicitly with ``allow_online``.
    """
    report = {"rendered": [], "skipped": []}
    for language in languages:
        for phrase_index in range(len(FILLERS.get(language, []))):
            for speed in speeds:
                try:
                    audio = filler_audio(language, voice, speed, phrase_index)
                    report["rendered"].append(
                        {"language": language, "voice": voice, "speed": speed,
                         "index": phrase_index, "bytes": len(audio["data"]),
                         "cache_hit": bool(audio.get("cache_hit"))})
                except Exception as error:  # a missing checkpoint should not abort the build
                    report["skipped"].append(
                        {"language": language, "voice": voice, "speed": speed,
                         "index": phrase_index, "error": type(error).__name__})
    report["cache_telemetry"] = tts_cache.get_cache().telemetry()
    return report
