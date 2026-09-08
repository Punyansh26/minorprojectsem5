"""Run with: conda activate minor && python -m streamlit run app.py."""

import json
from hashlib import sha256
from uuid import uuid4

import streamlit as st

from assistant import is_confirmation, run_turn
from config import API_KEY, CHAT_MODEL, MAX_TEXT_CHARS, STT_MODEL, STT_LANGUAGE, STT_DEVICE, TTS_VOICE
from mcp_client import direct, inspect_server
from responses import LANGUAGES, render
from voice import prepare_recording, synthesize, transcribe, transcription_error

st.set_page_config(page_title="किसान साथी — MCP Demo", page_icon="🌾", layout="wide")


def initialize():
    """Keep each browser's identity, transcript, and cart view separate."""
    defaults = {"session_id": str(uuid4()), "messages": [], "traces": [], "timings": {},
                "preview": None, "draft": "", "audio": None, "asr": {}, "last_warning": None,
                "search_results": None, "last_manual": None, "processed_recording": None}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize()
s = st.session_state
st.title("🌾 किसान साथी / Kisan Saathi")
st.caption("बोलकर सामान खोजें, दाम पूछें और टोकरी बनाएँ। • Synthetic catalogue · Demo orders only")

with st.sidebar:
    language = LANGUAGES[st.selectbox("भाषा / Language", list(LANGUAGES))]
    api_key = API_KEY
    if api_key:
        st.caption("Groq key loaded from server configuration.")
    else:
        api_key = st.text_input("Groq API key", type="password",
                                help="Or configure GROQ_API_KEY in demo/.env and restart the app.")
    st.caption(f"Chat: {CHAT_MODEL}\n\nSpeech recognition: {STT_MODEL}")
    st.caption(f"Local STT: {STT_LANGUAGE} on {STT_DEVICE.upper()} · Local VITS voice: {TTS_VOICE}. First speech use loads the models.")
    speak = st.checkbox("जवाब सुनें / Spoken replies", value=False,
                        help="Uses the project's local Chhattisgarhi VITS model. Choose Hindi or Chhattisgarhi for speech.")
    if not api_key:
        st.info("Add a Groq key for conversation. Local transcription and catalogue/cart buttons work without a key.")
    if st.button("नई बातचीत / New session"):
        for key in ["session_id", "messages", "traces", "timings", "preview", "draft", "audio", "asr", "last_warning", "discovery", "search_results", "last_manual", "processed_recording"]:
            s.pop(key, None)
        st.rerun()


def refresh():
    """Read server facts via MCP rather than inferring UI state from chat."""
    s.discovery = inspect_server(s.session_id, str(uuid4()))


if "discovery" not in s:
    try:
        with st.spinner("MCP server से जुड़ रहे हैं / Connecting…"):
            refresh()
    except Exception:
        st.error("MCP server could not start. Activate conda minor, install requirements, and retry.")
        if st.button("Retry MCP connection"):
            st.rerun()
        st.stop()


def remember(output, traces, user_text, timings=None):
    """Render and optionally speak only a confirmed backend result."""
    s.messages.extend([{"role": "user", "content": user_text},
                       {"role": "assistant", "content": render(output, language)}])
    s.messages = s.messages[-30:]
    s.traces = (s.traces + traces)[-60:]
    s.timings = timings or {}
    if output.get("response_template_id") == "checkout_preview":
        s.preview = output
    elif output.get("response_template_id") in {"added", "removed", "order"}:
        s.preview = None
    make_audio(s.messages[-1]["content"])


def make_audio(text):
    """Keep TTS failure independent from shopping success."""
    s.audio = None
    if speak:
        try:
            s.audio, elapsed = synthesize(text, language)
            s.timings["tts_ms"] = elapsed
        except ValueError as exc:
            s.last_warning = str(exc)
        except Exception:
            s.last_warning = "Spoken reply is unavailable. Your shopping result is shown below; try again later."


def manual(name, args, label, confirmation_token=""):
    """Route every manual mutation through the same MCP tool boundary."""
    try:
        with st.spinner("काम हो रहा है / Working…"):
            output, traces = direct(s.session_id, str(uuid4()), name, args, confirmation_token=confirmation_token)
            s.last_warning = None
            remember(output, traces, label)
            s.last_manual = render(output, language)
            if name == "search_products" and output.get("ok"):
                s.search_results = [p["product_id"] for p in output["products"]]
            refresh()
    except Exception:
        s.last_warning = "MCP connection failed. Refresh the cart before repeating a change; it may already have completed."
    st.rerun()


def submit_request(text, *, spoken=False):
    """Show the recognized request and keep one conversation path for speech and typing."""
    history = list(s.messages)
    s.messages.append({"role": "user", "content": text, "source": "voice" if spoken else "text"})
    s.audio = None
    s.last_warning = None
    try:
        with st.spinner("जवाब तैयार हो रहा है / Preparing your reply…"):
            if s.preview and is_confirmation(text):
                output, traces = direct(s.session_id, str(uuid4()), "confirm_checkout", {},
                                        confirmation_token=s.preview["confirmation_token"])
                turn = {"text": render(output, language), "traces": traces,
                        "outputs": [output], "timings": {}, "warning": None}
            else:
                turn = run_turn(text, language, api_key, s.session_id, str(uuid4()), history)
            s.messages.append({"role": "assistant", "content": turn["text"]})
            s.messages = s.messages[-30:]
            s.traces = (s.traces + turn["traces"])[-60:]
            asr_timings = {k: v for k, v in s.asr.items() if k.endswith("_ms")} if spoken else {}
            s.timings = {**turn["timings"], **asr_timings}
            s.last_warning = turn["warning"]
            for output in turn["outputs"]:
                if output.get("response_template_id") == "checkout_preview":
                    s.preview = output
                elif output.get("response_template_id") in {"added", "removed", "order"}:
                    s.preview = None
            make_audio(turn["text"])
            refresh()
    except Exception:
        s.last_warning = "The request could not finish. Refresh the cart to check its state before trying again."


talk, shop_tab, debug = st.tabs(["बातचीत / Talk", "सामान और टोकरी / Shop", "MCP proof / Developer"])
with talk:
    st.subheader("🎙️ बोलकर बात करें / Speak to your assistant")
    st.write("माइक दबाएँ, बोलें, फिर रोकें — आपकी बात और जवाब नीचे दिखेंगे।")
    st.caption("Press the microphone, speak, then press Stop. Speech is transcribed locally; the transcript goes to Groq for shopping actions.")
    if not api_key:
        st.info("You can transcribe locally now. Add a Groq key to act on the transcript.")
    recording = st.audio_input("माइक दबाकर बोलें / Press to speak", key=f"voice_{s.session_id}",
                               disabled=False,
                               help="Allow microphone access when your browser asks. Use localhost or HTTPS.")
    recording_id = (getattr(recording, "file_id", None) or sha256(recording.getvalue()).hexdigest()) if recording is not None else None
    if recording is not None and recording_id != s.processed_recording:
        # Claim the recording before any provider/tool call so reruns cannot repeat a write.
        s.processed_recording = recording_id
        s.audio = None
        s.asr = {}
        s.last_warning = None
        try:
            with st.spinner("आपकी बात सुन रहे हैं / Transcribing…"):
                audio = prepare_recording(recording.getvalue())
                s.asr = transcribe(audio, api_key, language)
        except ValueError as exc:
            s.last_warning = str(exc)
        except Exception as exc:
            s.last_warning = transcription_error(exc)
        else:
            st.info(f"आपने कहा / You said: {s.asr['text']}")
            if api_key:
                submit_request(s.asr["text"], spoken=True)
            else:
                s.messages.append({"role": "user", "content": s.asr["text"], "source": "voice"})
                s.last_warning = "Transcript ready. Configure GROQ_API_KEY to submit shopping requests."
        st.rerun()
    with st.expander("या लिखें / Type instead"):
        with st.form("typed_request", clear_on_submit=True):
            text = st.text_area("आपकी बात / Your request", key="draft", max_chars=MAX_TEXT_CHARS,
                                placeholder="मोला धान के बीज के दाम बतावव")
            submitted = st.form_submit_button("भेजें / Send", type="primary", disabled=not api_key)
        if submitted:
            if text.strip():
                submit_request(text.strip())
                st.rerun()
            else:
                st.info("कृपया अपनी बात लिखें / Please enter a request.")
    if s.last_warning:
        st.warning(s.last_warning)
    for msg in s.messages:
        with st.chat_message(msg["role"]):
            st.caption("जवाब / AI reply" if msg["role"] == "assistant" else
                       "आपने कहा / You said" if msg.get("source") == "voice" else "आप / You")
            st.write(msg["content"])
    if s.audio:
        st.audio(s.audio, format="audio/wav", autoplay=True)
        st.caption("If autoplay is blocked, press Play. Use Pause to stop the reply.")
    if s.preview:
        st.warning(render(s.preview, language))
        if st.button("डेमो ऑर्डर पक्का करें / Confirm demo order", key="confirm_talk"):
            manual("confirm_checkout", {}, "Confirm demo order", s.preview["confirmation_token"])
        if st.button("अभी नहीं / Cancel preview", key="cancel_talk"):
            s.preview = None
            st.rerun()

with shop_tab:
    if s.last_manual:
        st.info(s.last_manual)
    if s.last_warning:
        st.warning(s.last_warning)
    catalogue_col, cart_col = st.columns([3, 2])
    with catalogue_col:
        st.subheader("सामान / Catalogue")
        query = st.text_input("खोजें / Search", placeholder="धान, beej, khurpi…")
        if st.button("खोजें / Find"):
            manual("search_products", {"query": query}, f"Search: {query}")
        if s.search_results is not None and st.button("सभी सामान / Show all"):
            s.search_results = None
            st.rerun()
        for p in s.discovery["catalogue"]["products"]:
            if s.search_results is not None and p["product_id"] not in s.search_results:
                continue
            with st.container(border=True):
                st.write(f"**{p['name'] if language == 'en' else p['name_hi']}**")
                st.caption(f"{p['product_id']} · {p['price_display']} / {p['unit']} · Stock: {p['stock']}")
                quantity = st.number_input("संख्या / Count", min_value=1, max_value=max(1, min(p["stock"], 100)),
                                           value=1, step=1, key="qty_" + p["product_id"])
                a, b = st.columns(2)
                if a.button("जोड़ें / Add", key="add_" + p["product_id"], disabled=p["stock"] == 0):
                    manual("add_to_cart", {"product_id": p["product_id"], "quantity": quantity, "unit": p["unit"]},
                           f"Add {quantity} {p['unit']} × {p['name_hi']}")
                if b.button("जानकारी / Details", key="details_" + p["product_id"]):
                    manual("get_product_details", {"product_id": p["product_id"]}, f"Details: {p['name_hi']}")
    with cart_col:
        st.subheader("टोकरी / Cart")
        cart = s.discovery["cart"]
        if not cart["items"]:
            st.write("टोकरी खाली है / Your cart is empty")
        for item in cart["items"]:
            st.write(f"{item['quantity']} × {item['name'] if language == 'en' else item['name_hi']} — {item['line_total_display']}")
            if st.button("हटाएँ / Remove", key="remove_" + item["cart_item_id"]):
                manual("remove_from_cart", {"cart_item_id": item["cart_item_id"]}, f"Remove {item['name_hi']}")
        st.metric("कुल / Total", cart["total_display"])
        if st.button("टोकरी फिर देखें / Refresh cart"):
            manual("view_cart", {}, "View cart")
        if st.button("डेमो चेकआउट / Checkout", disabled=not cart["items"]):
            manual("checkout", {}, "Prepare demo checkout")
        if s.preview:
            st.write(render(s.preview, language))
            if st.button("पुष्टि / Confirm demo order", key="confirm_shop"):
                manual("confirm_checkout", {}, "Confirm demo order", s.preview["confirmation_token"])

with debug:
    st.success(f"Connected: {s.discovery['server']} · MCP {s.discovery['protocol_version']} · stdio")
    st.caption("Browser → Python MCP client → separate MCP server → local JSON. Groq selects tools; Python executes them over MCP.")
    with st.expander(f"Discovered tools ({len(s.discovery['tools'])})"):
        st.json(s.discovery["tools"])
    st.write("Latest stage timings (ms)")
    st.json(s.timings)
    st.write("Actual tool calls (most recent first)")
    for i, trace in enumerate(reversed(s.traces)):
        with st.expander(f"{trace['tool']} · {trace['duration_ms']} ms", expanded=i == 0):
            st.json(trace)
    st.download_button("Download tool trace (JSON)", json.dumps({"schema": "shopping.demo.v1", "model": CHAT_MODEL,
                       "timings": s.timings, "calls": s.traces}, ensure_ascii=False, indent=2),
                       file_name="mcp-demo-trace.json", mime="application/json")
    st.caption("Export includes tool arguments/results; no API keys, raw recordings, or full conversation. Review before sharing.")
