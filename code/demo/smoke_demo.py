"""Check real MCP shopping locally, with optional synthetic live speech checks."""

import argparse
import asyncio
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from assistant import run_turn
from config import API_KEY, API_TIMEOUT, CHAT_MODEL, STT_MODEL
from mcp_client import connect, invoke
from voice import synthesize, transcribe


def require(condition, message):
    """Keep smoke assertions active even when Python runs with optimization."""
    if not condition:
        raise RuntimeError(message)


async def check_mcp(path):
    """Exercise discovery, rejection, replay, and confirmed checkout over stdio."""
    traces = []
    async with connect("smoke", "shopping", path) as (session, tools, schemas, init):
        require(len(tools) == 12, "Expected 12 shopping tools")
        product = await invoke(session, schemas, "resolve_product", {"mention": "धान"}, traces)
        require(product.get("product", {}).get("product_id") == "SEED01", "Paddy resolution failed")
        args = {"product_id": "SEED01", "quantity": 2, "unit": "pack"}
        invalid = await invoke(session, schemas, "add_to_cart", {**args, "session_id": "other"}, traces)
        require(not invalid["ok"], "Host identity injection was accepted")
        rejected = await session.call_tool("add_to_cart", arguments={**args, "quantity": 0})
        require(rejected.isError, "Server accepted an invalid quantity")
        added = await invoke(session, schemas, "add_to_cart", args, traces)
        require(added.get("total_paise") == 90000, "Expected two packs totaling 900 rupees")
        replay = await invoke(session, schemas, "add_to_cart", args, traces)
        require(replay == added, "Retry changed the cart twice")
        ambiguous = await invoke(session, schemas, "resolve_product", {"mention": "जैविक खाद"}, traces)
        require(ambiguous.get("response_template_id") == "ambiguous", "Ambiguous manure was guessed")
        unavailable = await invoke(session, schemas, "add_to_cart",
                                   {"product_id": "TOOL04", "quantity": 1, "unit": "pair"}, traces)
        require(unavailable.get("error") == "insufficient_stock", "Out-of-stock item was accepted")
        rate = await invoke(session, schemas, "calculate_required_quantity",
                            {"product_id": "SEED01", "area_value": 2, "area_unit": "acre"}, traces)
        require(rate.get("error") == "unverified_rate_metadata", "Unverified field rate was returned")
        preview = await invoke(session, schemas, "checkout", {}, traces)
        denied = await invoke(session, schemas, "confirm_checkout", {}, traces)
        require(denied.get("error") == "confirmation_required", "Checkout bypassed host confirmation")
        require(all("confirmation_token" not in t["result"] for t in traces), "Trace exposed confirmation capability")
        protocol = init.protocolVersion
        server = init.serverInfo.name
    async with connect("other", "isolated", path) as (session, _, schemas, _):
        cart = await invoke(session, schemas, "view_cart", {}, [])
        require(cart["items"] == [], "Another session can see the smoke cart")
    async with connect("smoke", "confirmed", path, preview["confirmation_token"]) as (session, _, schemas, _):
        order = await invoke(session, schemas, "confirm_checkout", {}, traces)
        require(order.get("response_template_id") == "order", "Confirmed checkout failed")
        require(await invoke(session, schemas, "confirm_checkout", {}, traces) == order,
                "Checkout replay created a different order")
        cart = await invoke(session, schemas, "view_cart", {}, traces)
        require(cart["items"] == [], "Checkout did not clear the cart")
    return {"status": "passed", "server": server, "protocol_version": protocol,
            "tools": len(tools), "recorded_calls": len(traces), "total_paise": 90000}


def check_live(path):
    """Verify local speech and live Groq routing using only synthetic shopping input."""
    if not API_KEY:
        return {"status": "skipped", "reason": "GROQ_API_KEY is not configured"}
    speech, tts_ms = synthesize("धान के बीज का दाम बताओ।", "hne")
    # Resample the local VITS WAV in memory; never write a recording to disk.
    converted = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
         "-f", "s16le", "pipe:1"], input=speech, capture_output=True,
        check=True, timeout=API_TIMEOUT)
    import io
    import wave
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(converted.stdout)
    asr = transcribe(buffer.getvalue(), API_KEY, "hne")
    turn = run_turn(asr["text"], "hne", API_KEY, "live-smoke", "price", state_path=path)
    require(not turn["warning"], "Live model request failed or returned an invalid tool call")
    require(any(t["tool"] == "check_price" and t["result"].get("ok") for t in turn["traces"]),
            "Live model did not complete the requested price lookup")
    reply, reply_ms = synthesize(turn["text"], "hne")
    return {"status": "passed", "chat_model": CHAT_MODEL, "stt_model": STT_MODEL,
            "asr_language": asr["asr_language"], "input_tts_ms": tts_ms,
            "asr_ms": asr["asr_ms"], "reply_tts_ms": reply_ms,
            "reply_audio_bytes": len(reply), "turn_timings": turn["timings"],
            "tools_called": [t["tool"] for t in turn["traces"]]}


def main():
    """Print shareable verification results without keys, capabilities, or audio."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="Also call local VITS/STT and Groq using synthetic speech (requires ffmpeg and a key)")
    args = parser.parse_args()
    started = perf_counter()
    report = {}
    with TemporaryDirectory(prefix="farmer-demo-smoke-") as directory:
        path = Path(directory) / "shop.json"
        checks = {"mcp": lambda: asyncio.run(check_mcp(path))}
        if args.live:
            checks["live"] = lambda: check_live(path)
        for name, check in checks.items():
            try:
                report[name] = check()
            except Exception as exc:
                # Provider exception bodies may contain request details.
                report[name] = {"status": "failed", "error_type": type(exc).__name__}
    report["elapsed_ms"] = round((perf_counter() - started) * 1000, 1)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(value["status"] == "passed" for value in report.values() if isinstance(value, dict)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
