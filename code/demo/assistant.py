"""Bounded Groq tool selection over a real MCP connection."""

import asyncio
import json
import re
from time import perf_counter

from groq import AsyncGroq, APIConnectionError
from rapidfuzz import fuzz

from config import API_TIMEOUT, CHAT_MODEL, STATE_PATH, MAX_ROUNDS, MAX_TEXT_CHARS
from mcp_client import connect, invoke
from responses import render
from shop import result

SYSTEM = """You route requests for a farmer shopping demo. Understand Chhattisgarhi,
Hindi, English and Romanized code-switching (mola=I want, tokri=cart, dhaan=paddy,
beej=seed, bori=bag, daal do=add, hata do=remove). Use only the provided tools.
Always get facts from tools. Never invent product IDs, stock, prices, application
rates or quantities.
Be tolerant of transcription errors, dialect variations, and phonetic spelling from speech recognition (e.g. dhan/dhaan, gehu/gehun, tamatar/tamater, khurpi/khurpa, hasiya/hansiya, vermi/compost).
Interpret the user's approximate meaning and intent rather than requiring word-by-word matches.
Extract the intended product and call resolve_product or search_products to find it.
Understand spoken numbers and units:
- 'ek'/'aik'=1, 'do'=2, 'teen'=3, 'char'=4, 'panch'=5.
- Package words: 'bori'/'katta' -> bag, 'pack'/'packet'/'thaili' -> pack, 'nag'/'piece' -> piece, 'jodi' -> pair.
If the user asks to add an unambiguous product with count or single mention (e.g. 'dhaan beej daal do' or 'ek dhaan beej'), resolve the product and add 1 of its package unit. Only ask quantity clarification if the quantity cannot be reasonably inferred.
For cart queries or checking what's in the cart, call view_cart.
For price requests, call check_price after resolving the product.
If multiple matching products exist, ask clarification.
Never choose a product based on crop symptoms. For disease diagnosis, pesticide selection, dosage, treatment or crop symptoms, call refuse_and_refer immediately and do not modify the cart in that turn.
For field area quantities, use calculate_required_quantity.
For checkout, call checkout to prepare a preview.
After completing the requested task, stop calling tools. Keep tool calls sequential.
Free-form final text is not displayed: the app renders grounded result templates.
"""

# A conservative demo guard, not a validated safety classifier. Responses are also
# fixed templates, and no tool can return a treatment recommendation or dosage.
SAFETY_PATTERN = re.compile(
    r"diagnos|disease|dosage|dose\b|treat(?:ment)?|pesticide.*(?:which|how)|"
    r"(?:which|how).*pesticide|spray|yellow\s+leav|बीमारी|रोग|इलाज|छिड़क|छिडक|"
    r"खुराक|दवाई|दवा|कीटनाशक|पीले.*पत्त|पत्त.*पीले|bimari|dawai|kitnashak|chid[ak]",
    re.IGNORECASE,
)
CONFIRM_PHRASES = {"confirm demo order", "demo order pakka karo",
                    "डेमो ऑर्डर पक्का करो", "डेमो ऑर्डर की पुष्टि करें"}
QUICK_ACTIONS = {
    "view cart": "view_cart", "show cart": "view_cart", "show my cart": "view_cart",
    "tokri dikhao": "view_cart", "tokri dikhaav": "view_cart",
    "टोकरी दिखाओ": "view_cart", "टोकरी दिखावव": "view_cart", "टोकरी दिखाइए": "view_cart",
    "checkout": "checkout", "demo checkout": "checkout",
    "demo checkout karo": "checkout", "डेमो चेकआउट करो": "checkout",
}

# Fuzzy thresholds — confirmation is security-sensitive so kept guarded against negations.
_CONFIRM_THRESHOLD = 80
_QUICK_ACTION_THRESHOLD = 75


def _fuzzy_best(text: str, candidates, threshold: int):
    """Return the best fuzzy-matching candidate key (or None) above threshold."""
    clean = text.casefold().strip().rstrip(".!।")
    best_key, best_score = None, 0
    for candidate in candidates:
        score = max(fuzz.ratio(clean, candidate.casefold()),
                    fuzz.token_sort_ratio(clean, candidate.casefold()))
        if score > best_score:
            best_key, best_score = candidate, score
    return best_key if best_score >= threshold else None


def is_confirmation(text: str) -> bool:
    """Require an approximate confirmation phrase while strictly rejecting negations."""
    clean = text.casefold().strip().rstrip(".!।")
    if any(neg in clean.split() for neg in ["don't", "dont", "not", "mat", "nahi", "nhi", "न", "नहीं", "मत"]):
        return False
    return _fuzzy_best(text, CONFIRM_PHRASES, _CONFIRM_THRESHOLD) is not None


def fuzzy_quick_action(text: str):
    """Return the tool name for the best-matching quick action, or None."""
    key = _fuzzy_best(text, QUICK_ACTIONS, _QUICK_ACTION_THRESHOLD)
    return QUICK_ACTIONS[key] if key else None


def provider_warning(exc: Exception) -> str:
    """Identify actionable provider failures without exposing request bodies or keys."""
    status = getattr(exc, "status_code", None)
    reasons = {401: "Groq rejected the API key. Update GROQ_API_KEY in demo/.env and restart.",
               403: "This Groq account cannot access the configured model.",
               404: "The configured Groq model is unavailable. Update GROQ_CHAT_MODEL in demo/.env and restart.",
               429: "Groq's rate limit was reached. Wait before submitting another request.",
               400: "Groq rejected the model/tool request. Check the configured model's tool support."}
    if status in reasons:
        reason = reasons[status]
    elif isinstance(exc, APIConnectionError):
        reason = "Could not connect to Groq. Check the internet connection."
    else:
        reason = "Groq could not finish this request. Try again shortly."
    return reason + " Check the cart before repeating an action."


async def run_async(text, language, api_key, session_id, turn_id, history=None,
                    state_path=STATE_PATH, client=None):
    """Run a small tool loop, preserving successful tool results if Groq later fails."""
    if not text.strip() or len(text) > MAX_TEXT_CHARS:
        raise ValueError("Please enter a request between 1 and 1500 characters.")
    traces, outputs = [], []
    timings = {"llm_ms": 0.0}
    started = perf_counter()
    warning = None
    owned_client = client is None
    client = client or AsyncGroq(api_key=api_key, timeout=API_TIMEOUT, max_retries=0)
    try:
        async with connect(session_id, turn_id, state_path) as (session, discovered, schemas, init):
            timings["mcp_connect_ms"] = round((perf_counter() - started) * 1000, 1)
            allowed = {t.name for t in discovered} - {"confirm_checkout"}
            tools = [{"type": "function", "function": {"name": t.name,
                      "description": t.description, "parameters": schemas[t.name]}}
                     for t in discovered if t.name in allowed]
            messages = [{"role": "system", "content": SYSTEM}]
            for item in (history or [])[-8:]:
                messages.append({"role": item["role"], "content": item["content"][:2000]})
            messages.append({"role": "user", "content": text})
            if SAFETY_PATTERN.search(text):
                outputs.append(await invoke(session, schemas, "refuse_and_refer", {}, traces))
            elif (quick := fuzzy_quick_action(text)) is not None:
                outputs.append(await invoke(session, schemas, quick, {}, traces))
            else:
                for _ in range(MAX_ROUNDS):
                    tick = perf_counter()
                    try:
                        completion = await client.chat.completions.create(
                            model=CHAT_MODEL, messages=messages, tools=tools,
                            tool_choice="required" if not outputs else "auto",
                            parallel_tool_calls=False, temperature=0, max_completion_tokens=1200)
                    except Exception as exc:
                        warning = provider_warning(exc)
                        break
                    finally:
                        timings["llm_ms"] += round((perf_counter() - tick) * 1000, 1)
                    message = completion.choices[0].message
                    calls = message.tool_calls or []
                    if not calls:
                        break
                    messages.append(message.model_dump(exclude_none=True))
                    # Validate the entire batch before any mutation: a model can
                    # still emit parallel calls despite parallel_tool_calls=False.
                    parsed = []
                    invalid = False
                    for call in calls:
                        try:
                            args = json.loads(call.function.arguments)
                            if not isinstance(args, dict) or call.function.name not in allowed:
                                raise ValueError("Invalid tool")
                            from jsonschema import validate
                            validate(args, schemas[call.function.name])
                            parsed.append((call, args))
                        except Exception:
                            invalid = True
                    if invalid or len(parsed) != 1:
                        outputs.append(result("clarification", reason="repeat"))
                        warning = "The model returned an invalid or parallel tool request. No tools in that batch were executed."
                        break
                    call, args = parsed[0]
                    output = await invoke(session, schemas, call.function.name, args, traces)
                    outputs.append(output)
                    model_output = {k: v for k, v in output.items() if k != "confirmation_token"}
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": json.dumps(model_output, ensure_ascii=False)})
                    if output.get("response_template_id") in {"referral", "clarification", "ambiguous", "checkout_preview"}:
                        break
                    # Grounded templates already provide the reply after a write. Avoid
                    # spending another free-tier request just to ask the model to stop.
                    if output.get("response_template_id") in {"added", "removed"}:
                        break
            if not outputs:
                outputs.append(result("clarification", reason="repeat"))
            # A later explanation failure cannot erase confirmation of an earlier write.
            visible = [o for o in outputs if o.get("response_template_id") in {"added", "removed"}]
            if not visible or visible[-1] is not outputs[-1]:
                visible.append(outputs[-1])
            response = "\n\n".join(render(o, language) for o in visible)
            cart = await invoke(session, schemas, "view_cart", {}, [])
            timings["total_ms"] = round((perf_counter() - started) * 1000, 1)
            return {"text": response, "outputs": outputs, "traces": traces, "cart": cart,
                    "timings": timings, "warning": warning, "model": CHAT_MODEL,
                    "protocol_version": init.protocolVersion}
    finally:
        if owned_client:
            await client.close()


def run_turn(*args, **kwargs):
    """Keep async resources scoped to one synchronous Streamlit turn."""
    return asyncio.run(run_async(*args, **kwargs))
