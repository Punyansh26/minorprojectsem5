"""Temporary FutureWork Task 01 measurement: verbalization, retrieval (kbb), VITS, Whisper. Not part of the repo.
Run from code/demo2 with DEMO2_DATA_DIR pointing to a scratch dir so repository state is untouched."""
import io, json, os, re, statistics, subprocess, sys, time
import numpy as np, psutil, soundfile as sf

os.environ["DEMO2_DATA_DIR"] = "/tmp/fw01_data"
sys.path.insert(0, os.getcwd())
import settings as cfg
cfg.configure_agent()
sys.path.insert(0, str(cfg.AGENT_ROOT))
import speech
import verbalization

proc = psutil.Process()
OUT = {"date": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "stt_device_env": cfg.STT_DEVICE, "whisper_model": cfg.WHISPER_MODEL,
       "tts_device": cfg.TTS_DEVICE, "threads": cfg.SPEECH_THREADS}


def pct(a, q):
    return float(np.percentile(np.array(a, dtype=float), q))


def smi():
    return subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                          capture_output=True, text=True).stdout.strip()


def wer(ref, hyp):
    r, h = ref.split(), hyp.split()
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(len(r), 1)


DATA = cfg.CODE_ROOT / "demo2/data/upgrade-20260930"
base = json.load(open(DATA / "baseline/results.json"))
cases = json.load(open(cfg.ROOT / "evaluation/upgrade-20260930/cases.json"))

# ---------------- 1. verbalization
rows = []
for r in base:
    if r["response_status"] == "answered":
        rows.append((r["answer_text"], r["language"]))
times = []
for text, lang in rows:
    t = time.perf_counter()
    for _ in range(50):
        verbalization.normalize(text, lang if lang in ("hindi", "english", "hinglish") else "hindi")
    times.append((time.perf_counter() - t) / 50 * 1000)
OUT["verbalization_ms"] = {"n_texts": len(times), "p50": pct(times, 50), "p95": pct(times, 95), "max": max(times)}
print("verbalization", OUT["verbalization_ms"], flush=True)

# ---------------- 2. retrieval on the served kbb release
from assistant.retrieval import retrieve, get_release_engine
t = time.perf_counter()
eng = get_release_engine()
OUT["retrieval_engine_init_s"] = time.perf_counter() - t
OUT["retrieval_engine"] = type(eng).__name__
print("engine init", OUT["retrieval_engine"], OUT["retrieval_engine_init_s"], flush=True)
t = time.perf_counter()
retrieve("What is the tuition fee?")
OUT["retrieval_first_query_s"] = time.perf_counter() - t
per_lang, allt, hits = {}, [], []
for c in cases:
    t = time.perf_counter()
    res = retrieve(c["question"])
    ms = (time.perf_counter() - t) * 1000
    per_lang.setdefault(c["language"], []).append(ms)
    allt.append(ms)
    if c["expected"] == "answerable" and c.get("expected_blocks"):
        ids = [x.block_id for x in res]
        hits.append(any(b in ids for b in c["expected_blocks"]))
OUT["retrieval_warm_ms"] = {"n": len(allt), "p50": pct(allt, 50), "p95": pct(allt, 95), "max": max(allt),
                            **{k: {"p50": pct(v, 50), "p95": pct(v, 95)} for k, v in per_lang.items()}}
OUT["retrieval_expected_block_hit"] = {"hit": sum(hits), "n": len(hits)}
print("retrieval", OUT["retrieval_warm_ms"], OUT["retrieval_expected_block_hit"], flush=True)

# ---------------- 3. VITS
answers = []
seen = set()
for r in base:
    if r["response_status"] == "answered" and r["language"] == "hindi" and r["answer_text"] not in seen:
        seen.add(r["answer_text"])
        answers.append(r["answer_text"])
speakable, unspeakable = [], []
for a in answers:
    try:
        speakable.append((a, speech.prepare_speech(a, "Female")))
    except Exception as e:
        unspeakable.append((a[:60], type(e).__name__, str(e)[:90]))
OUT["tts_prepare"] = {"hindi_answered_unique": len(answers), "speakable": len(speakable), "rejected": len(unspeakable),
                      "reject_examples": unspeakable[:3]}
print("tts prepare", OUT["tts_prepare"], flush=True)
tts_rows, clips = [], []
rss0 = proc.memory_info().rss
for idx, (orig, spoken) in enumerate(speakable[:10]):
    voice = "Female"
    cached = voice in speech._SYNTHESIZERS
    t = time.perf_counter()
    audio = speech.make_audio(orig, "hindi", voice)
    dt = time.perf_counter() - t
    info = sf.info(io.BytesIO(audio["data"]))
    tts_rows.append({"idx": idx, "cold": not cached, "chars": len(audio["spoken_text"]), "audio_s": info.duration,
                     "synth_s": dt, "rtf": dt / info.duration, "rss_mb": proc.memory_info().rss / 2**20})
    clips.append((audio["spoken_text"], audio["data"], info.duration))
    print("tts", tts_rows[-1], flush=True)
# second voice cold + warm
t = time.perf_counter()
a = speech.make_audio(speakable[0][0], "hindi", "Male")
male_cold = time.perf_counter() - t
t = time.perf_counter()
a2 = speech.make_audio(speakable[0][0], "hindi", "Male")
male_warm = time.perf_counter() - t
OUT["tts"] = {"rows": tts_rows, "male_cold_s": male_cold, "male_warm_s": male_warm,
              "rss_after_both_voices_mb": proc.memory_info().rss / 2**20, "rss_before_mb": rss0 / 2**20}
warm = [r for r in tts_rows if not r["cold"]]
if warm:
    OUT["tts"]["warm_rtf_p50"] = pct([r["rtf"] for r in warm], 50)
    OUT["tts"]["warm_synth_s_p50"] = pct([r["synth_s"] for r in warm], 50)
    OUT["tts"]["warm_chars_per_s"] = sum(r["chars"] for r in warm) / sum(r["synth_s"] for r in warm)
# first-chunk latency (sentence-level), relevant for future streaming: time to synthesize first chunk only
first_chunks = []
syn = speech._SYNTHESIZERS["Female"]
for orig, spoken in speakable[:8]:
    chunk = speech._chunks(spoken)[0]
    t = time.perf_counter()
    w = syn.tts(text=chunk)
    first_chunks.append({"chars": len(chunk), "s": time.perf_counter() - t, "audio_s": len(w) / syn.output_sample_rate})
OUT["tts"]["first_chunk"] = first_chunks
print("tts first chunk", first_chunks, flush=True)

# ---------------- 4. Whisper ASR on synthetic VITS speech
test_clips = [c for c in clips if 0.3 <= c[2] <= 30]
OUT["asr_clips_audio_s"] = [round(c[2], 2) for c in test_clips]


def run_asr(label, device):
    cfg.STT_DEVICE = device
    speech._WHISPER = None
    res = []
    for i, (ref, data, dur) in enumerate(test_clips):
        t = time.perf_counter()
        text = speech.transcribe(data, "Hindi")
        dt = time.perf_counter() - t
        res.append({"i": i, "cold": i == 0, "audio_s": dur, "seconds": dt, "rtf": dt / dur, "wer": wer(ref, text)})
        print(label, res[-1], flush=True)
    dev = getattr(getattr(speech._WHISPER, "model", None), "device", "?")
    return {"device_requested": device, "ct2_device": str(dev), "rows": res, "gpu_mem_used_mib_after": smi(),
            "warm_s_p50": pct([r["seconds"] for r in res[1:]], 50) if len(res) > 1 else None,
            "warm_rtf_p50": pct([r["rtf"] for r in res[1:]], 50) if len(res) > 1 else None,
            "wer_mean": float(np.mean([r["wer"] for r in res]))}


OUT["gpu_mem_before_asr_mib"] = smi()
OUT["asr_cpu"] = run_asr("asr-cpu", "cpu")
OUT["asr_auto"] = run_asr("asr-auto", "auto")
json.dump(OUT, open("/tmp/fw01_speech_result.json", "w"), indent=1, ensure_ascii=False)
print("DONE", flush=True)
