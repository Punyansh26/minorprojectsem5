"""Explicit synthetic browser fixture: fake providers, real app/jobs/storage/DOM."""
import io
import json
import os
from pathlib import Path
import runpy
import sys
import time

import numpy as np
import soundfile as sf
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['DEMO2_DATA_DIR']='/tmp/demo2-browser-upgrade'
import agent_bridge
import speech
import health
import importlib
importlib.reload(health)


@st.cache_resource
def fixtures():
    counts=dict(ask=0,speech=0,stt=0)
    def save():Path('/tmp/demo2-browser-counts.json').write_text(json.dumps(counts))
    def ask(question,session,profile,**kwargs):
        counts['ask']+=1;save();time.sleep(.2)
        return dict(answer_text='Reviewed fixture answer: tuition is ₹90,000; this is not the total fee.',
            language='english',response_status='answered',sources=[dict(source_file='public-fixture.pdf',page_number=11,
            quote='Tuition 90000',audience='Synthetic browser test')],rag_metrics=dict(model_calls=3),ticket_id=None)
    def audio(*args,**kwargs):
        counts['speech']+=1;save();time.sleep(8)
        if not kwargs.get('allow_online'):
            raise speech.SpeechError('Online speech is off. Enable it to speak this English answer.')
        buffer=io.BytesIO();sf.write(buffer,np.zeros(1600),16000,format='WAV')
        return dict(data=buffer.getvalue(),mime='audio/wav',extension='wav',spoken_text=args[0],provider='Synthetic fixture')
    def transcribe(data,language):
        counts['stt']+=1;save();speech.decode_audio(data)
        if counts['stt']==1:raise RuntimeError('Synthetic first transcription failure')
        return 'What is the public fixture tuition fee?'
    agent_bridge.ask=ask;speech.make_audio=audio;speech.transcribe=transcribe
    return counts


fixtures()
runpy.run_path(str(ROOT/'app.py'),run_name='__main__')
