import os, sys, json, time
os.environ["DEMO2_DATA_DIR"]="/tmp/fw01_data"
sys.path.insert(0, os.getcwd())
import settings as cfg
cfg.configure_agent(); sys.path.insert(0,str(cfg.AGENT_ROOT))
# 1. why does Whisper 'auto' land on CPU?
from faster_whisper import WhisperModel
try:
    m=WhisperModel("small",device="cuda",compute_type="float16"); print("CUDA load OK")
    import numpy as np
    try:
        list(m.transcribe(np.zeros(16000*2,dtype="float32"),language="hi")[0]); print("CUDA transcribe OK")
    except Exception as e: print("CUDA transcribe ERR:",type(e).__name__,str(e)[:200])
except Exception as e: print("CUDA load ERR:",type(e).__name__,str(e)[:200])
# 2. required-term recall on served kbb release
from assistant.retrieval import retrieve
cases=json.load(open(cfg.ROOT/"evaluation/upgrade-20260930/cases.json"))
import re
def norm(s): return re.sub(r"\s+"," ",s).lower()
res={}
for c in cases:
    if c["expected"]!="answerable": continue
    chunks=retrieve(c["question"])
    for k in (3,6,8):
        text=norm(" ".join(x.text for x in chunks[:k]))
        ok=all(norm(t) in text for t in c.get("required_terms",[]))
        d=res.setdefault(c["language"],{}).setdefault(k,[0,0]); d[0]+=ok; d[1]+=1
tot={k:[sum(res[l][k][0] for l in res),sum(res[l][k][1] for l in res)] for k in (3,6,8)}
print("required-terms present in top-k text:",json.dumps(res),"TOTAL",tot)
