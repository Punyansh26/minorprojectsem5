"""Run the existing three-trial JEV gate on an isolated artifact after public QA drains."""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--kb-state',type=Path,required=True)
    parser.add_argument('--wait-for',type=Path)
    parser.add_argument('--count',type=int,default=12)
    args=parser.parse_args()
    if args.wait_for:
        deadline=time.monotonic()+1800
        while time.monotonic()<deadline:
            if args.wait_for.exists() and len(json.loads(args.wait_for.read_text()))>=args.count:
                break
            time.sleep(1)
        else:raise TimeoutError('Prior isolated workload did not finish')
    os.environ.update(KB_STATE_DIR=str(args.kb_state.resolve()),LLM_PROVIDER='ollama',JEV_ROUTING_MODE='off',
                      HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Institute-voice-agent/institute-assistant'))
    from assistant.jev.paired_benchmark import benchmark
    result=benchmark(args.artifacts.resolve(),quick=False,trials=3)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
