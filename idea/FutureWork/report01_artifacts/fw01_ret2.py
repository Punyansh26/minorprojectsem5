import os,sys,json,time
os.environ["DEMO2_DATA_DIR"]="/tmp/fw01_data"
sys.path.insert(0,os.getcwd())
import settings as cfg
cfg.configure_agent(); sys.path.insert(0,str(cfg.AGENT_ROOT))
from assistant.retrieval import retrieve, get_release_engine
eng=get_release_engine(); retrieve("warm up")
cases=json.load(open(cfg.ROOT/"evaluation/upgrade-20260930/cases.json"))
rows=[]
for c in cases:
    t=time.perf_counter(); res=retrieve(c["question"]); ms=(time.perf_counter()-t)*1000
    rows.append((ms,c["topic"],c["language"],len(res),res[0].kind if res else None,res[0].score if res else None))
rows.sort(reverse=True)
import numpy as np
a=np.array([r[0] for r in rows])
print("n>100ms",int((a>100).sum()),"n<50ms",int((a<50).sum()),"of",len(a))
from collections import Counter
print("slow topics",Counter(r[1] for r in rows if r[0]>100))
print("fast topics",Counter(r[1] for r in rows if r[0]<=100).most_common(6))
print("slow sample",[(round(r[0]),r[1],r[2],r[4]) for r in rows[:4]])
t=time.perf_counter(); eng._engine.embedder.embed_query("What is the tuition fee for B.Tech in 2026?"); print("embed_query ms",(time.perf_counter()-t)*1000)
t=time.perf_counter(); eng._engine.embedder.embed_query("What is the tuition fee for B.Tech in 2026?"); print("embed_query ms (2nd)",(time.perf_counter()-t)*1000)
