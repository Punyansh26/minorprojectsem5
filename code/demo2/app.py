"""Streamlit entrypoint for the institute's speech-to-speech helpdesk."""
from hashlib import sha256
from pathlib import Path

import streamlit as st

import settings as cfg
import workflow
from agent_bridge import valid_profile_email

st.set_page_config(page_title="IIIT-NR | Voice helpdesk", page_icon="🎙️", layout="wide")
st.markdown("""<style>
.stApp {background:#f5f8fc; color:#18324d}
.block-container {max-width:1120px; padding-top:2.4rem}
h1,h2,h3 {color:#163b5d; letter-spacing:-0.025em}
[data-testid="stSidebar"] {background:#e8f0f5}
[data-testid="stChatMessage"] {background:white; border-radius:12px; padding:1.2rem}
.intro {color:#48637c; font-size:1.1rem; max-width:48rem; line-height:1.6}
</style>""", unsafe_allow_html=True)

if "conversation" not in st.session_state:
    st.session_state.conversation = workflow.new_session()
session = st.session_state.conversation

with st.sidebar:
    st.header("Your conversation")
    language = st.selectbox("Recording language", cfg.INPUT_LANGUAGES)
    st.caption("Replies follow the language of your question.")
    voice = st.selectbox("Voice", cfg.VOICES)
    speed = st.slider("Speaking speed", min_value=0.7, max_value=1.4, value=1.0, step=0.1)
    spoken = st.toggle("Generate spoken replies", value=True)
    autoplay = st.toggle("Play new replies automatically", value=True)
    st.caption("Hindi uses the local voice. English and Hinglish use an online voice service.")
    with st.expander("Student details (optional)"):
        student_id = st.text_input("Student reference", max_chars=100)
        email = st.text_input("Follow-up email", max_chars=254)
        category = st.selectbox("Admission category", ["general", "CG"])
        st.caption("These details provide context; they do not verify your identity.")
    if st.button("New conversation", use_container_width=True):
        st.session_state.conversation = workflow.new_session()
        st.rerun()
    st.divider()
    st.caption("Staff-review requests create local drafts. Email delivery and reminders are disabled in this demo.")
    with st.expander("Demo setup"):
        for label, path in (("Institute agent", cfg.AGENT_ROOT / "assistant/graph.py"),
                            ("Knowledge index", cfg.AGENT_ROOT / "chroma_index/chroma.sqlite3"),
                            ("Female voice", cfg.TTS_ROOT / "Female/best_model.pth"),
                            ("Male voice", cfg.TTS_ROOT / "Male/best_model.pth")):
            st.write(f"{'✓' if path.is_file() else 'Missing:'} {label}")
        st.caption("Speech models load on first use. Chhattisgarhi understanding is experimental.")

st.title("Ask your institute.")
st.markdown('<p class="intro">Speak naturally in Hindi, English, or Hinglish. Get answers about '
            'admissions, hostel life, fees, and academics—with the source material close at hand.</p>',
            unsafe_allow_html=True)

profile = {"student_id": student_id, "student_email": email, "student_category": category}
profile_valid = valid_profile_email(email)
if not profile_valid:
    st.warning("Enter a valid follow-up email in the sidebar or leave it blank.")

with st.container(border=True):
    st.subheader("Start with your voice")
    mode = st.radio("Audio source", ["Microphone", "Upload a recording"], horizontal=True,
                    label_visibility="collapsed")
    if mode == "Microphone":
        recording = st.audio_input("Record your question", key=f"mic-{session['id']}", disabled=not profile_valid)
    else:
        recording = st.file_uploader("Choose a WAV or FLAC recording", type=["wav", "flac"],
                                     key=f"upload-{session['id']}", disabled=not profile_valid)
    st.caption("Up to 30 seconds. Stop recording to send your question automatically. "
               "Microphone access requires localhost or HTTPS.")

if recording is not None and profile_valid:
    data = recording.getvalue()
    recording_id = f"{mode}:{getattr(recording, 'file_id', sha256(data).hexdigest())}"
    if recording_id not in session["consumed_audio"]:
        try:
            with st.status("Listening to your recording…", expanded=True) as status:
                question = workflow.consume_recording(session, recording_id, data, language)
                if question:
                    st.write(question)
                    status.update(label="Finding your answer and preparing speech…")
                    workflow.run_turn(session, question, profile, voice, speed, spoken, turn_id=recording_id)
                    status.update(label="Your reply is ready", state="complete", expanded=False)
                else:
                    status.update(label="No clear speech detected. Record again or type your question.", state="error")
        except Exception as error:
            st.error(f"The recording could not be transcribed. Try a shorter recording or type below. ({type(error).__name__})")

question = st.chat_input("Or type your question…", max_chars=cfg.MAX_TEXT_CHARS, disabled=not profile_valid)
if question:
    with st.spinner("Finding your answer and preparing speech…"):
        workflow.run_turn(session, question, profile, voice, speed, spoken)

if not session["turns"]:
    st.caption("Try: ‘B.Tech admission kaise hota hai?’ or ‘What hostel facilities are available?’")

for turn in session["turns"]:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        if turn["error"]:
            st.error(turn["error"])
            continue
        st.write(turn["answer_text"])
        if turn.get("response_status") == "unavailable":
            st.caption("The answer service is temporarily unavailable. You can ask again later.")
        if turn.get("ticket_id"):
            st.caption(f"Local staff-review draft #{turn['ticket_id']}")
        if turn.get("sources"):
            with st.expander("View sources"):
                for source in turn["sources"]:
                    label = Path(source.get("source_file", "Source")).name
                    if source.get("page_number", 0) > 0:
                        label += f" — page {source['page_number']}"
                    st.write(label)
                    st.text(source.get("quote", ""))
        audio = turn.get("audio")
        if audio:
            st.audio(audio["data"], format=audio["mime"],
                     autoplay=autoplay and session["autoplay_id"] == turn["id"])
            if session["autoplay_id"] == turn["id"]:
                session["autoplay_id"] = None
            st.download_button("Download reply", data=audio["data"],
                file_name=f"reply-{sha256(turn['id'].encode()).hexdigest()[:8]}.{audio['extension']}",
                mime=audio["mime"], key=f"download-{turn['id']}")
            with st.expander("Spoken text"):
                st.write(audio["spoken_text"])
                st.caption(audio["provider"] + ". Pronunciation text may differ from the displayed answer.")
        else:
            if turn.get("audio_error"):
                st.warning(turn["audio_error"])
            if turn["answer_text"] and st.button("Retry audio" if turn.get("audio_error") else "Speak this reply",
                                                key=f"speak-{turn['id']}"):
                with st.spinner("Preparing speech…"):
                    workflow.speak_turn(turn, voice, speed)
                session["autoplay_id"] = turn["id"] if turn["audio"] else None
                st.rerun()
        st.caption(f"Answer: {turn.get('agent_seconds', 0):.1f}s · Speech: {turn.get('speech_seconds', 0):.1f}s")
