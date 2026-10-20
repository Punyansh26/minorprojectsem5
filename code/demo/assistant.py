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


# --- Task 08 §b: deterministic tool retrieval (rule map) -------------------
#
# The model does not need every schema every turn. We keep a small always-on
# safety/clarify set, add tools suggested by cheap keyword rules, and fall back
# to the full catalogue when the rules are not confident. Narrowing only hides
# tools from the model; it never bypasses the schema validation in mcp_client
# or the confirm-before-write gate. `confirm_checkout` is never exposed here
# (the loop already removes it), so the model still cannot self-confirm.

# Always kept so safety and clarification can fire on any turn.
_ALWAYS_TOOLS = {"refuse_and_refer", "request_clarification"}

# Keyword → candidate tools. Patterns are intentionally broad and multilingual;
# a miss is harmless because of the full-set fallback below.
_TOOL_RULES = (
    (re.compile(r"cart|tokri|tokari|टोकरी|basket", re.I), {"view_cart"}),
    (re.compile(r"price|daam|दाम|कीमत|rate|cost|kitne ka|कितने का", re.I),
     {"resolve_product", "check_price", "get_product_details"}),
    (re.compile(r"remove|hata|हटा|nikaal|निकाल|kam kar|कम कर", re.I),
     {"view_cart", "remove_from_cart"}),
    (re.compile(r"add|daal|डाल|जोड़|jod|chahiy|चाहि|mola|le lo|ले लो|le aao", re.I),
     {"resolve_product", "search_products", "add_to_cart"}),
    (re.compile(r"checkout|order|ऑर्डर|चेकआउट|kharid|खरीद|bill|बिल", re.I),
     {"checkout", "view_cart"}),
    (re.compile(r"area|acre|hectare|एकड़|हेक्टेयर|बीघा|bigha|khet|खेत|kitna", re.I),
     {"calculate_required_quantity", "resolve_product"}),
    (re.compile(r"search|dhoond|ढूंढ|khoj|खोज|list|suchi|सूची|kaun|कौन|what.*sell", re.I),
     {"search_products"}),
)


def select_tools(text: str, available: set) -> set:
    """Narrow the exposed tool set with cheap rules; fall back to all on low confidence.

    Returns a subset of ``available``. Always includes the safety/clarify tools so
    a diagnosis request or an ambiguous turn can still be handled. If no rule
    matches (low confidence), returns the full available set unchanged so the
    model never loses the tool it actually needs (Task 08 §b risk guard).
    """
    chosen = set()
    for pattern, tools in _TOOL_RULES:
        if pattern.search(text):
            chosen |= tools
    if not chosen:
        return set(available)
    chosen |= _ALWAYS_TOOLS
    narrowed = chosen & available
    # Keep at least the safety/clarify fallback even if the intersection is thin.
    return narrowed or set(available)


# --- Task 08 §e: deterministic slot filling for the common add turn --------
#
# "ek dhaan beej daal do" / "do khurpi chahiye" resolve to exactly one product
# with an inferable count and the product's own package unit. Doing this with
# rules removes the resolve_product + add_to_cart LLM rounds (two model calls →
# zero) on the most frequent write. It is deliberately conservative: it only
# fires when the product resolves uniquely AND a count is parseable, and it
# never fires on a safety, negation, or question turn. Everything else still
# goes to the model. The actual write still runs through the MCP add_to_cart
# tool with full schema validation and idempotency — this only pre-computes the
# arguments the model would otherwise have produced.

_SPOKEN_NUMBERS = {
    "ek": 1, "aik": 1, "एक": 1, "ik": 1, "one": 1,
    "do": 2, "दो": 2, "two": 2, "don": 2,
    "teen": 3, "तीन": 3, "three": 3,
    "char": 4, "चार": 4, "four": 4, "chaar": 4,
    "panch": 5, "पांच": 5, "पाँच": 5, "five": 5, "paanch": 5,
    "chhe": 6, "che": 6, "छह": 6, "छे": 6, "six": 6,
    "saat": 7, "सात": 7, "seven": 7,
    "aath": 8, "आठ": 8, "eight": 8,
    "nau": 9, "नौ": 9, "nine": 9,
    "das": 10, "दस": 10, "ten": 10,
}

# Add-intent markers in the supported languages. The add fast path only fires
# when one of these is present, so a bare "dhaan beej" (which could be a price
# or search intent) is left to the model.
_ADD_INTENT = re.compile(
    r"\b(daal|daalo|daal\s*do|daldo|add|jod|jodo|जोड़|डाल|le\s*lo|ले\s*लो|chahiy|चाहि)\b",
    re.I,
)
_NEGATIONS = ("don't", "dont", "not", "mat", "nahi", "nhi", "न", "नहीं", "मत", "remove", "hata", "हटा")
_QUESTION = re.compile(r"\?|price|daam|दाम|kitne|कितने|kaun|कौन|how|what|kya|क्या|दिखा|dikha")


def _parse_count(text: str):
    """Return an integer count from digits or spoken numbers, or None if absent."""
    digits = re.search(r"\b(\d{1,3})\b", text)
    if digits:
        value = int(digits.group(1))
        return value if 1 <= value <= 100 else None
    for token in text.casefold().split():
        clean = token.strip(".!।,")
        if clean in _SPOKEN_NUMBERS:
            return _SPOKEN_NUMBERS[clean]
    return None


def add_intent(text: str):
    """Return a parsed count for a clear single-product add turn, else None.

    Returns the integer count to add (defaulting to 1 when an add verb is
    present without a spoken number), or None when this turn is not a safe
    deterministic add. Conservative guards: no safety turns, no negations, no
    questions/price/cart queries. Product resolution and the write itself are
    performed over MCP by the caller, preserving the single-transport invariant
    and full schema validation.
    """
    clean = text.casefold()
    if SAFETY_PATTERN.search(text):
        return None
    if any(neg in clean.split() or neg in clean for neg in _NEGATIONS):
        return None
    if not _ADD_INTENT.search(text):
        return None
    if _QUESTION.search(text):
        return None
    count = _parse_count(text)
    return 1 if count is None else count


# --- Task 08 §h: content-free spoken acknowledgement -----------------------
#
# A short "working on it" fills the second silence while a tool runs (R02). It
# must never assert a fact, so the strings below are purely procedural. The app
# can pre-synthesise and play these; the assistant only selects which to speak.
ACKNOWLEDGEMENTS = {
    "en": "One moment, checking.",
    "hi": "एक मिनट, देख रहा हूँ।",
    "hne": "एक मिनट, देखत हवं।",
}


def acknowledgement(language: str) -> str:
    """Return a content-free acknowledgement for the given language code."""
    return ACKNOWLEDGEMENTS.get(language, ACKNOWLEDGEMENTS["hi"])


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
            # Task 08 §c: trust the server's readOnlyHint annotation to decide
            # which tools may run in a parallel batch. Fall back to a fixed set
            # if a server omits annotations, so a missing hint can never make a
            # write look read-only.
            _READ_ONLY_FALLBACK = {"search_products", "resolve_product", "get_product_details",
                                   "check_price", "view_cart", "calculate_required_quantity",
                                   "request_clarification", "refuse_and_refer"}
            read_only = set()
            for t in discovered:
                hint = getattr(getattr(t, "annotations", None), "readOnlyHint", None)
                if hint is True:
                    read_only.add(t.name)
            if not read_only:
                read_only = set(_READ_ONLY_FALLBACK)
            read_only &= allowed
            # Task 08 §b: narrow the exposed tools with cheap rules (keeps the
            # safety/clarify set, falls back to all on low confidence).
            exposed = select_tools(text, allowed)
            timings["tools_exposed"] = len(exposed)
            timings["tools_available"] = len(allowed)
            tools = [{"type": "function", "function": {"name": t.name,
                      "description": t.description, "parameters": schemas[t.name]}}
                     for t in discovered if t.name in exposed]
            messages = [{"role": "system", "content": SYSTEM}]
            for item in (history or [])[-8:]:
                messages.append({"role": item["role"], "content": item["content"][:2000]})
            messages.append({"role": "user", "content": text})
            used_llm = False
            if SAFETY_PATTERN.search(text):
                outputs.append(await invoke(session, schemas, "refuse_and_refer", {}, traces))
            elif (quick := fuzzy_quick_action(text)) is not None:
                outputs.append(await invoke(session, schemas, quick, {}, traces))
            elif (count := add_intent(text)) is not None and \
                    (resolved := await invoke(session, schemas, "resolve_product", {"mention": text}, traces)) \
                    .get("response_template_id") == "product":
                # Task 08 §e: deterministic single-product add. resolve_product
                # (read-only) ran above over MCP; if it named exactly one in-stock
                # product, add it with its own unit and the parsed count — zero
                # LLM calls. Otherwise fall through to the model below.
                product = resolved["product"]
                if product.get("stock", 0) > 0:
                    outputs.append(await invoke(session, schemas, "add_to_cart",
                                   {"product_id": product["product_id"], "quantity": count,
                                    "unit": product["unit"]}, traces))
                else:
                    outputs.append(result("clarification", reason="product"))
            else:
                used_llm = True
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
                    # Validate the entire batch before any execution: a model can
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
                    # Task 08 §c: allow a validated multi-call batch ONLY when every
                    # call is read-only (annotation-gated), running them together on
                    # the one MCP session. Any write, or any invalid call, keeps the
                    # strict single-call invariant: writes are never parallelised and
                    # the batch is rejected without mutation.
                    all_read_only = parsed and all(c.function.name in read_only for c, _ in parsed)
                    if invalid or (len(parsed) != 1 and not all_read_only):
                        outputs.append(result("clarification", reason="repeat"))
                        warning = "The model returned an invalid or parallel tool request. No tools in that batch were executed."
                        break
                    if len(parsed) > 1:
                        batch = await asyncio.gather(*[
                            invoke(session, schemas, c.function.name, a, traces) for c, a in parsed])
                        for (call, _), output in zip(parsed, batch):
                            outputs.append(output)
                            model_output = {k: v for k, v in output.items() if k != "confirmation_token"}
                            messages.append({"role": "tool", "tool_call_id": call.id,
                                             "content": json.dumps(model_output, ensure_ascii=False)})
                        # Reads are terminal here: speak the grounded result(s) and stop.
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
                    "used_llm": used_llm, "acknowledgement": acknowledgement(language),
                    "protocol_version": init.protocolVersion}
    finally:
        if owned_client:
            await client.close()


def run_turn(*args, **kwargs):
    """Keep async resources scoped to one synchronous Streamlit turn."""
    return asyncio.run(run_async(*args, **kwargs))
