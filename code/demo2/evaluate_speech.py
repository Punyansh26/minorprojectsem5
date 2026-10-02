"""Measure public synthetic speech mechanics; never label it native-speaker validation."""
import argparse
import io
import json
from pathlib import Path
import time
import psutil
import soundfile as sf

import settings as cfg
import speech


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--online',action='store_true',help='Explicitly consent to sending fixed public test text to Edge speech')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    cfg.configure_agent()
    rows=[];process=psutil.Process()
    sentence='सुरक्षा जमा ₹15,000 वापसी योग्य है। शिक्षण शुल्क ₹90,000 है।'
    for index,voice in enumerate(['Female','Female','Male','Male','Female']):
        cached=voice in speech._SYNTHESIZERS;started=time.monotonic()
        audio=speech.make_audio(sentence,'hindi',voice)
        info=sf.info(io.BytesIO(audio['data']))
        (args.output/f'{index}-{voice}.wav').write_bytes(audio['data'])
        rows.append(dict(voice=voice,cached_before=cached,seconds=time.monotonic()-started,
            rss_bytes=process.memory_info().rss,sample_rate=info.samplerate,duration=info.duration,
            spoken_text=audio['spoken_text'],cached_voices=list(speech._SYNTHESIZERS)))
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    started=time.monotonic()
    transcript=speech.transcribe((args.output/'4-Female.wav').read_bytes(),'Hindi')
    stt=dict(seconds=time.monotonic()-started,transcript=transcript,reference=sentence,
             source='synthetic VITS playback; not a microphone/native recording')
    online=[]
    if args.online:
        for language,text in [('english','The tuition fee is 90,000 rupees. This is not the total fee.'),
                ('hinglish','Tuition fee 90,000 rupaye hai. Yeh total fee nahi hai.')]:
            started=time.monotonic()
            try:
                audio=speech.make_audio(text,language,'Female',allow_online=True)
                (args.output/f'{language}.mp3').write_bytes(audio['data'])
                online.append(dict(language=language,seconds=time.monotonic()-started,bytes=len(audio['data']),spoken_text=audio['spoken_text']))
            except Exception as error:
                online.append(dict(language=language,seconds=time.monotonic()-started,error=type(error).__name__))
    report=dict(synthesis=rows,stt=stt,online=online,human_listening=False,native_speech_validated=False)
    (args.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(stt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
