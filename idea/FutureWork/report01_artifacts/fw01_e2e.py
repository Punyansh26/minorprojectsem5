"""Composed voice-turn timing on the effective Demo 2 configuration; scratch data dir; not part of repo."""
import io, json, os, subprocess, sys, time, uuid, urllib.request
os.environ["DEMO2_DATA_DIR"]="/tmp/fw01_e2e_data"
sys.path.insert(0, os.getcwd())
import settings as cfg
cfg.configure_agent(); sys.path.insert(0,str(cfg.AGENT_ROOT))
import soundfile as sf, numpy as np
import speech, agent_bridge
cases=json.load(open(cfg.ROOT/"evaluation/upgrade-20260930/cases.json"))
hi=[c for c in cases if c["language"]=="hindi" and c["expected"]=="answerable"]
picked,seen=[],set()
for c in hi:
    try: speech.prepare_speech(c["question"],"Female")
    except Exception: continue
    if c["topic"] in seen and len(picked)<5: continue
    seen.add(c["topic"]); picked.append(c)
    if len(picked)==7: break
print("topics",[c["topic"] for c in picked],flush=True)
# question audio (synthetic, built outside the measured path)
qaudio=[speech.make_audio(c["question"],"hindi","Female")["data"] for c in picked]
qdur=[sf.info(io.BytesIO(a)).duration for a in qaudio]
def ps():
    d=json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/ps").read())
    return [{"gpu_pct":round(100*m["size_vram"]/m["size"],1)} for m in d.get("models",[])]
rows=[]
for i,(c,a,dur) in enumerate(zip(picked,qaudio,qdur)):
    row={"i":i,"id":c["id"],"question_audio_s":round(dur,2)}
    t=time.perf_counter(); transcript=speech.transcribe(a,"Hindi"); row["asr_s"]=time.perf_counter()-t
    row["asr_text_ok"]=bool(transcript)
    t=time.perf_counter()
    r=agent_bridge.ask(c["question"],str(uuid.uuid4()),{},provider="ollama")   # reference text: synthetic ASR WER ~0.8
    row["agent_s"]=time.perf_counter()-t
    m=r["rag_metrics"]; row["status"]=r["response_status"]; row["lang"]=r["language"]; row["calls"]=m.get("model_calls")
    row["stage_ms"]={k:round(v) for k,v in m["stage_ms"].items()}
    row["answer_chars"]=len(r["answer_text"] or "")
    try:
        t=time.perf_counter(); au=speech.make_audio(r["answer_text"],r["language"],"Female")
        row["tts_s"]=time.perf_counter()-t; row["answer_audio_s"]=round(sf.info(io.BytesIO(au["data"])).duration,2)
        row["spoken_chars"]=len(au["spoken_text"])
    except Exception as e:
        row["tts_error"]=type(e).__name__
        row["tts_s"]=None
    row["ollama_ps"]=ps()
    rows.append(row); print(json.dumps(row,ensure_ascii=False),flush=True)
json.dump(rows,open("/tmp/fw01_e2e_result.json","w"),ensure_ascii=False,indent=1)
urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate",json.dumps({"model":"qwen3.5:9b","keep_alive":0}).encode(),{"Content-Type":"application/json"}))
print("DONE",flush=True)
