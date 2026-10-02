"""Render reviewed answers independently of bounded background model and speech jobs."""
from hashlib import sha256
from pathlib import Path
from time import monotonic
from uuid import uuid4

import streamlit as st

import settings as cfg
import workflow
from agent_bridge import valid_profile_email
from health import runtime_health
from jobs import manager, TERMINAL

st.set_page_config(page_title="IIIT-NR | Voice helpdesk",page_icon="🎙️",layout="wide")
st.markdown("""<style>
.block-container {max-width:1120px;padding-top:2rem}
[data-testid="stChatMessage"] {border:1px solid #d4dde6;border-radius:12px}
</style>""",unsafe_allow_html=True)
if "conversation" not in st.session_state:
    st.session_state.conversation = workflow.new_session()
session = st.session_state.conversation
runtime = manager()

with st.sidebar:
    st.header("Your conversation")
    provider = st.selectbox("Answer model",["ollama","groq"],
        format_func=lambda p:"Local · Ollama" if p=="ollama" else "Groq · Cloud",key="llm_provider")
    st.caption("Groq sends your question, conversation context and source excerpts to the cloud when selected.")
    language = st.selectbox("Recording language",cfg.INPUT_LANGUAGES)
    voice = st.selectbox("Voice",cfg.VOICES)
    speed = st.slider("Speaking speed",min_value=.7,max_value=1.4,value=1.,step=.1)
    spoken = st.toggle("Generate spoken replies",value=True)
    online = st.toggle("Allow online English/Hinglish speech",value=False,key="online_speech")
    st.caption("Online speech sends answer text to the voice service. Hindi speech uses the local voice.")
    autoplay = st.toggle("Play new replies automatically",value=True)
    with st.expander("Student details (optional)"):
        student_id = st.text_input("Student reference",max_chars=100)
        email = st.text_input("Follow-up email",max_chars=254)
        category = st.selectbox("Admission category",["general","CG"])
        st.caption("These details provide context; they do not verify your identity.")
    st.caption(f"Conversations and local drafts expire after {cfg.RETENTION_SECONDS/3600:g} hours. New conversation starts fresh; Delete conversation erases this conversation.")
    if st.button("New conversation",use_container_width=True):
        runtime.cancel(session["id"])
        st.session_state.conversation = workflow.new_session()
        st.rerun()
    if st.button("Delete conversation",use_container_width=True):
        session["delete_pending"] = True
        runtime.cancel(session["id"])
    st.caption("Staff-review requests save local drafts. Email delivery and reminders are disabled.")
    with st.expander("Runtime status"):
        health = runtime_health()
        st.write("Knowledge release:",health.get("release") or "Missing")
        st.write("Knowledge stores:","Ready" if health["release_ok"] else "Unavailable")
        st.write("Release integrity:",health.get("release_integrity","unavailable"))
        st.caption(f"Source owners unassigned: {health.get('sources_unassigned','?')} \u00b7 Reviews overdue: {health.get('sources_review_overdue','?')} \u00b7 Evidence blocks: {health.get('evidence_blocks','?')}")
        jev_info = f"{health['jev_mode']} \u00b7 {health['jev_artifact']} \u00b7 {health['jev_activation']}"
        if "jev_backend" in health:
            jev_info += f" \u00b7 {health['jev_backend']}"
        st.write("Router:", jev_info)
        st.caption("Shadow routing measures predictions; it does not accelerate answers.")
        with st.expander("Environment"):
            if "environment" in health:
                st.write("**System:**")
                st.json(health["environment"])
            if "dependencies" in health:
                st.write("**Dependencies:**")
                st.json(health["dependencies"])
        st.json(runtime.stats())

st.title("Ask your institute.")
st.write("Speak or type in Hindi, English, or Hinglish. Read the reviewed answer and its sources while speech is prepared.")
st.caption("Chhattisgarhi recording is experimental; replies may use Hindi. This is a supervised local demonstration.")
profile = {"student_id":student_id,"student_email":email,"student_category":category}
profile_valid = valid_profile_email(email)
if not profile_valid:
    st.warning("Enter a valid follow-up email or leave it blank.")

ERRORS = {
    "busy":"The helpdesk is at capacity. Try again shortly.",
    "conversation_busy":"This conversation already has a request running. Wait or cancel it.",
    "queue_timeout":"The queue wait expired. Retry when the helpdesk is less busy.",
    "deadline_exceeded":"This request reached its time limit. You can retry it safely.",
    "storage_busy":"Conversation storage is busy. Your request can be retried safely.",
    "invalid_audio":"This recording could not be decoded. Use a mono/stereo WAV or FLAC, 0.3–30 seconds, up to 12 MB.",
    "no_speech":"No clear speech was detected. Retry transcription, record again, or type your question.",
    "turn_failed":"The request could not be completed. Check Runtime status and retry.",
    "conversation_expired":"This conversation has expired. Start a new conversation.",
    "request_conflict":"This request identifier belongs to a different submission. Start a new question.",
}

def submit(question,turn_id=None,data=None):
    turn_id = turn_id or str(uuid4())
    try:
        runtime.submit(session["id"],turn_id,question,profile,provider,voice,speed,spoken,online,data,language)
        if turn_id not in session.setdefault("job_ids",[]):
            session["job_ids"].append(turn_id)
        session["job_ids"] = session["job_ids"][-cfg.MAX_HISTORY_TURNS:]
        session["played"] = session.get("played",set()).intersection(session["job_ids"])
        session["first_visible"] = {k:v for k,v in session.get("first_visible",{}).items() if k in session["job_ids"]}
        return True
    except Exception as error:
        st.warning(ERRORS.get(str(error),"The request could not be submitted. Please retry."))
        return False

with st.container(border=True):
    st.subheader("Start with your voice")
    mode = st.radio("Audio source",["Microphone","Upload a recording"],horizontal=True,label_visibility="collapsed")
    recording = (st.audio_input("Record your question",key=f"mic-{session['id']}",disabled=not profile_valid)
                 if mode=="Microphone" else st.file_uploader("Choose a WAV or FLAC recording",type=["wav","flac"],
                    key=f"upload-{session['id']}",disabled=not profile_valid))
    st.caption("Stop recording to submit. Up to 30 seconds. Microphone access requires localhost or HTTPS.")
    if recording is not None and profile_valid:
        data = recording.getvalue()
        recording_id = "recording:"+sha256(data).hexdigest()
        existing = runtime.snapshot(session["id"],recording_id)
        if session.get("current_recording") != recording_id:
            if submit("",recording_id,data):
                session["current_recording"] = recording_id
        elif existing and existing["stage"]=="failed":
            if st.button("Retry transcription",key="retry-transcription"):
                runtime.retry(session["id"],recording_id,data)

question = st.chat_input("Or type your question…",max_chars=cfg.MAX_TEXT_CHARS,disabled=not profile_valid or session.get("delete_pending",False))
if question:
    submit(question)

LABELS = {"queued":"Waiting in the queue", "transcribing":"Transcribing your recording", "reasoning":"Starting your question",
    "routing":"Understanding your question", "routing_model":"Understanding your question", "retrieval":"Finding source evidence",
    "answer":"Preparing a grounded answer", "generation_model":"Preparing a grounded answer", "review_model":"Checking the answer against sources",
    "speech":"Preparing speech — reviewed text is ready", "saving_action":"Saving your local draft"}

@st.fragment(run_every=.5)
def conversation():
    if session.get("delete_pending"):
        if runtime.delete(session["id"]):
            st.session_state.conversation = workflow.new_session()
            st.rerun()
        st.info("Cancelling work and deleting this conversation…")
        return
    if not session.get("job_ids"):
        st.caption("Try: ‘B.Tech admission kaise hota hai?’ or ‘What hostel facilities are available?’")
    for turn_id in session.get("job_ids",[]):
        turn = runtime.snapshot(session["id"],turn_id)
        if not turn:
            continue
        with st.chat_message("user"):
            st.write(turn.get("question") or "Recorded question")
        with st.chat_message("assistant"):
            if turn.get("answer_text"):
                st.write(turn["answer_text"])
                session.setdefault("first_visible",{}).setdefault(turn_id,monotonic())
            stage = turn["stage"]
            if stage not in TERMINAL:
                st.status(LABELS.get(stage,"Processing your request"),expanded=False)
                if st.button("Cancel",key="cancel-"+turn_id):
                    runtime.cancel(session["id"],turn_id)
            if stage=="cancelled":
                st.caption("Request cancelled. Any draft already saved remains listed below.")
            if turn.get("error_code"):
                st.warning(ERRORS.get(turn["error_code"],"The request could not be completed."))
                if stage=="failed" and turn.get("question") and not turn_id.startswith("recording:"):
                    if st.button("Retry question",key="retry-"+turn_id):
                        runtime.retry(session["id"],turn_id)
            if turn.get("ticket_id"):
                st.caption(f"Local staff-review draft #{turn['ticket_id']}")
            if turn.get("response_status")=="unavailable":
                st.caption(turn.get("llm_error") or "The answer service is temporarily unavailable.")
            if turn.get("sources"):
                with st.expander("View sources"):
                    for source in turn["sources"]:
                        st.write(f"{Path(source.get('source_file','Source')).name} — page {source.get('page_number','?')}")
                        if source.get("source_url","").startswith(("https://","http://")):
                            st.link_button("Official source",source["source_url"])
                        for key in ("period","audience","conflict_note","scope_note"):
                            if source.get(key):
                                st.caption(source[key])
                        st.text(source.get("quote",""))
            audio = turn.get("audio")
            if audio:
                played = session.setdefault("played",set())
                st.audio(audio["data"],format=audio["mime"],autoplay=autoplay and turn_id not in played)
                played.add(turn_id)
                st.download_button("Download reply",data=audio["data"],file_name="reply."+audio["extension"],
                                   mime=audio["mime"],key="download-"+turn_id)
                with st.expander("Spoken text"):
                    st.write(audio["spoken_text"])
                    st.caption(audio["provider"])
            elif turn.get("answer_text") and stage in TERMINAL:
                if turn.get("audio_error"):
                    st.info(turn["audio_error"])
                if st.button("Retry audio" if turn.get("audio_error") else "Speak this reply",key="speak-"+turn_id):
                    runtime.retry_audio(session["id"],turn_id,voice,speed,online)
            if turn.get("answer_text"):
                metrics = turn.get("rag_metrics") or {}
                timings = turn.get("timings") or {}
                
                timing_parts = [f"Queue {timings.get('queue_seconds', 0):.1f}s"]
                if "stt_seconds" in timings:
                    timing_parts.append(f"STT {timings['stt_seconds']:.1f}s")
                timing_parts.append(f"Answer {turn.get('agent_seconds', 0):.1f}s")
                if "reviewed_text_seconds" in timings:
                    timing_parts.append(f"Text ready {timings['reviewed_text_seconds']:.1f}s")
                timing_parts.append(f"Speech {turn.get('speech_seconds', 0):.1f}s")
                if "audio_ready_seconds" in timings:
                    timing_parts.append(f"Total {timings['audio_ready_seconds']:.1f}s")
                    
                st.caption(f"{turn.get('llm_provider', provider)} · {metrics.get('model', '')} · {' · '.join(timing_parts)}")
                
                st.caption(f"Model calls: {metrics.get('model_calls', 0)} · Retrieval cache: {metrics.get('retrieval_cache', 'bypass')} · Draft cache: {metrics.get('draft_cache', 'bypass')}")
                
                if "stage_ms" in timings:
                    with st.expander("Timing breakdown"):
                        for stage, ms in timings["stage_ms"].items():
                            st.text(f"{stage}: {ms} ms")

conversation()
