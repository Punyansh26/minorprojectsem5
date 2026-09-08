"""Exercise keyless UI and real MCP cart actions with Streamlit's app harness."""

from streamlit.testing.v1 import AppTest
import pytest


def test_keyless_app_checkout(tmp_path, monkeypatch):
    import config
    import mcp_client
    from functools import partial

    monkeypatch.setenv("DEMO_STATE_PATH", str(tmp_path / "ui.json"))
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(mcp_client, "inspect_server", partial(mcp_client.inspect_server, state_path=tmp_path / "ui.json"))
    monkeypatch.setattr(mcp_client, "direct", partial(mcp_client.direct, state_path=tmp_path / "ui.json"))
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    assert "Connected" in app.success[0].value
    app.button(key="add_SEED01").click().run()
    assert not app.exception
    assert app.session_state["discovery"]["cart"]["item_count"] == 1
    next(b for b in app.button if b.label == "डेमो चेकआउट / Checkout").click().run()
    assert app.session_state["preview"]
    app.button(key="confirm_shop").click().run()
    assert not app.exception
    assert app.session_state["discovery"]["cart"]["items"] == []


@pytest.fixture
def microphone_app(tmp_path, monkeypatch):
    """Supply microphone events and provider doubles while retaining real MCP cart calls."""
    import config
    import mcp_client
    import streamlit
    import voice
    from functools import partial
    from io import BytesIO

    class Recording(BytesIO):
        file_id = "recording-1"

    recording = Recording(b"browser audio")
    events = {"recording": recording, "transcriptions": 0}
    monkeypatch.setattr(config, "API_KEY", "test-key")
    monkeypatch.setattr(mcp_client, "inspect_server", partial(mcp_client.inspect_server, state_path=tmp_path / "voice.json"))
    monkeypatch.setattr(mcp_client, "direct", partial(mcp_client.direct, state_path=tmp_path / "voice.json"))
    monkeypatch.setattr(streamlit, "audio_input", lambda *a, **kw: None if kw["disabled"] else events["recording"])
    monkeypatch.setattr(voice, "prepare_recording", lambda audio: audio)

    def transcribe(*args):
        events["transcriptions"] += 1
        return {"text": "धान के दो पैकेट टोकरी में डालो", "asr_ms": 12}

    monkeypatch.setattr(voice, "transcribe", transcribe)
    return events


def test_microphone_auto_send_and_rerun_deduplication(microphone_app, monkeypatch):
    import assistant
    import mcp_client
    from responses import render

    calls = []

    def run_turn(text, language, api_key, session_id, turn_id, history):
        calls.append(text)
        output, traces = mcp_client.direct(session_id, turn_id, "add_to_cart",
                                           {"product_id": "SEED01", "quantity": 2, "unit": "pack"})
        return {"text": render(output, language), "outputs": [output], "traces": traces,
                "timings": {"llm_ms": 1}, "warning": None}

    monkeypatch.setattr(assistant, "run_turn", run_turn)
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    assert microphone_app["transcriptions"] == 1
    assert len(calls) == 1
    assert app.session_state["discovery"]["cart"]["item_count"] == 2
    assert len(app.chat_message) == 2
    assert "You said" in app.chat_message[0].caption[0].value
    assert "धान के दो पैकेट" in app.chat_message[0].markdown[0].value
    assert "AI reply" in app.chat_message[1].caption[0].value
    assert "₹900.00" in app.chat_message[1].markdown[0].value
    assert not app.get("file_uploader")
    app.run()
    assert len(calls) == 1
    assert microphone_app["transcriptions"] == 1
    # A new recording may legitimately repeat exactly the same spoken command.
    microphone_app["recording"].file_id = "recording-2"
    app.run()
    assert not app.exception
    assert len(calls) == 2
    assert app.session_state["discovery"]["cart"]["item_count"] == 4


def test_transcript_survives_ai_failure_without_automatic_retry(microphone_app, monkeypatch):
    import assistant

    def unavailable(*args):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(assistant, "run_turn", unavailable)
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    assert len(app.chat_message) == 1
    assert "धान के दो पैकेट" in app.chat_message[0].markdown[0].value
    assert app.warning
    app.run()
    assert microphone_app["transcriptions"] == 1
    assert len(app.chat_message) == 1


def test_typed_form_submits_current_text(tmp_path, monkeypatch):
    import config
    import assistant
    import mcp_client
    from functools import partial
    from responses import render
    monkeypatch.setattr(config, "API_KEY", "configured-key")
    path = tmp_path / "typed.json"
    monkeypatch.setattr(mcp_client, "inspect_server", partial(mcp_client.inspect_server, state_path=path))
    monkeypatch.setattr(mcp_client, "direct", partial(mcp_client.direct, state_path=path))
    requests = []
    def run_turn(text, language, api_key, session_id, turn_id, history):
        requests.append(text)
        output, traces = mcp_client.direct(session_id, turn_id, "add_to_cart",
                                           {"product_id": "SEED01", "quantity": 2, "unit": "pack"})
        return {"text": render(output, language), "outputs": [output], "traces": traces,
                "timings": {}, "warning": None}
    monkeypatch.setattr(assistant, "run_turn", run_turn)
    app = AppTest.from_file("app.py", default_timeout=30).run()
    send = next(b for b in app.button if b.label == "भेजें / Send")
    assert not send.disabled
    app.text_area(key="draft").input("धान के दो पैकेट डालो")
    send.click().run()
    assert not app.exception
    assert requests == ["धान के दो पैकेट डालो"]
    assert app.session_state["discovery"]["cart"]["item_count"] == 2
    app.run()
    assert len(requests) == 1
