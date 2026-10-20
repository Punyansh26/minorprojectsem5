import os,sys,json,time,copy,uuid,urllib.request
os.environ["DEMO2_DATA_DIR"]="/tmp/fw01_g_data"; os.environ["RAG_CACHE_ENABLED"]="false"
sys.path.insert(0,os.getcwd())
import settings as cfg
cfg.configure_agent(); sys.path.insert(0,str(cfg.AGENT_ROOT))
import agent_bridge
from assistant import llm
captured=[]
client=llm._local_client(llm.settings.OLLAMA_BASE_URL,llm.settings.OLLAMA_TIMEOUT_SECONDS)
orig=client.post
def spy(url,*a,**k):
    if "json" in k and url.endswith("api/chat"): captured.append(copy.deepcopy(k["json"]))
    return orig(url,*a,**k)
client.post=spy
cases={c["id"]:c for c in json.load(open(cfg.ROOT/"evaluation/upgrade-20260930/cases.json"))}
def post(body):
    req=urllib.request.Request("http://127.0.0.1:11434/api/chat",json.dumps(body).encode(),{"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=600).read())
def simple(fmt):
    f=copy.deepcopy(fmt)
    if "$defs" in f and "Evidence" in f["$defs"]:
        f["$defs"]["Evidence"]={"type":"object","properties":{"source_id":{"type":"integer"},"quote":{"type":"string"}},"required":["source_id","quote"],"additionalProperties":False}
    return f
out=[]
for cid in ["tuition_english","cg_income_sc_english","semester1_fee_hindi"]:
    captured.clear()
    r=agent_bridge.ask(cases[cid]["question"],str(uuid.uuid4()),{},provider="ollama")
    gen=[b for b in captured if "oneOf" in json.dumps(b["format"].get("$defs",{}).get("Evidence",{}))]
    if not gen: print(cid,"no enum request captured",len(captured),flush=True); continue
    body=gen[0]
    enum_sz=sum(len(o["properties"]["quote"]["enum"]) for o in body["format"]["$defs"]["Evidence"]["oneOf"])
    enum_chars=sum(len(q) for o in body["format"]["$defs"]["Evidence"]["oneOf"] for q in o["properties"]["quote"]["enum"])
    res={"case":cid,"status":r["response_status"],"calls":len(captured),"enum_entries":enum_sz,"enum_chars":enum_chars,
         "format_json_bytes":len(json.dumps(body["format"])),"sources":len(body["format"]["$defs"]["Evidence"]["oneOf"])}
    for label,fmt in (("enum",body["format"]),("noenum",simple(body["format"])),("enum",body["format"]),("noenum",simple(body["format"]))):
        b=copy.deepcopy(body); b["format"]=fmt
        d=post(b)
        ec,ed=d.get("eval_count",0),d.get("eval_duration",0)/1e6
        res.setdefault(label,[]).append({"prompt_tokens":d.get("prompt_eval_count"),"prefill_ms":round(d.get("prompt_eval_duration",0)/1e6),
              "decode_tokens":ec,"decode_ms":round(ed),"ms_per_token":round(ed/ec,1) if ec else None,"total_s":round(d.get("total_duration",0)/1e9,2)})
    out.append(res); print(json.dumps(res),flush=True)
json.dump(out,open("/tmp/fw01_grammar_result.json","w"),indent=1)
post({"model":"qwen3.5:9b","keep_alive":0,"messages":[]})
print("DONE")
