"""Validate model decisions before they can affect replies or create local actions."""
import json
import math
import re
import time
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Literal

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import ensure_config
from langchain_groq import ChatGroq
from groq import RateLimitError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from assistant.config import settings
from assistant import operations

_LOCAL_LOCK = RLock()
_LOCAL_DIGESTS = {}
# Whether the local model advertises the "thinking" capability (/api/show).
# Ollama rejects the `think` request field with HTTP 400 for models that do not,
# so this gates whether `think` is sent at all. Cached per (base_url, model) and
# refreshed on the same lazy schedule as the digest.
_LOCAL_THINKING = {}


class LocalModelError(RuntimeError):
    """A safe, actionable message; never includes provider response bodies."""


def selected_provider(provider=None, config_settings=None):
    configured = config_settings or settings
    value = provider or ensure_config().get("configurable", {}).get("llm_provider") or configured.LLM_PROVIDER
    if value not in {"ollama", "groq"}:
        raise ValueError("LLM provider must be ollama or groq")
    return value


def model_identity(config_settings=None, provider=None):
    configured = config_settings or settings
    selected = selected_provider(provider, configured)
    return {"provider": selected,
            "model": configured.OLLAMA_MODEL if selected == "ollama" else configured.GROQ_CHAT_MODEL,
            "endpoint": configured.OLLAMA_BASE_URL if selected == "ollama" else "groq",
            "context": configured.OLLAMA_NUM_CTX if selected == "ollama" else None,
            "tokenizer": configured.OLLAMA_TOKENIZER_PATH if selected == "ollama" else None,
            "digest": _LOCAL_DIGESTS.get((configured.OLLAMA_BASE_URL, configured.OLLAMA_MODEL)) if selected == "ollama" else None,
            "temperature": 0, "max_tokens": configured.LLM_MAX_TOKENS,
            "repeat_penalty": 1.0 if selected == "ollama" else None,
            "presence_penalty": 0 if selected == "ollama" else None, "budget_version": 5}


@lru_cache(maxsize=4)
def _tokenizer(path):
    from tokenizers import Tokenizer
    path = str(Path(path).expanduser())
    if not Path(path).is_file():
        raise LocalModelError("Local tokenizer is missing. Run python setup_local.py in institute-assistant.")
    return Tokenizer.from_file(path)


def _messages(schema, instruction, payload):
    # Put the current question after older history. Small local models otherwise
    # sometimes answer the last historical user message instead of the current one.
    current_fields = ("last_resolved_query", "question", "original_message", "message")
    ordered = {key: value for key, value in payload.items() if key not in current_fields}
    ordered.update({key: payload[key] for key in current_fields if key in payload})
    if schema.__name__ == "RoutingDecision":
        instruction += ("\nThe message field is the NEWEST user request. Route and rewrite that field, "
                        "never the last user entry in history. For follow-ups, take the latest resolved_query "
                        "from last_resolved_query (not an older question in history) "
                        "and apply EVERY change requested in message, preserving all other dimensions. "
                        "The query field must always be in English, even for Hindi or Hinglish messages.")
    language = {"hindi": "Hindi using Devanagari script", "hinglish": "Hinglish using Roman Hindi",
                "english": "English"}.get(payload.get("language"))
    if language and schema.__name__ == "GroundedAnswer":
        instruction += (f"\nFor THIS response, write the answer field in {language}. "
                        "Keep evidence quotes in their original source language. "
                        "Answer only the original_message's specific question in 1-3 short sentences. "
                        "Exclude application steps, fees, quotas or eligibility unless the original question asks for them. "
                        "A rule about one admission quota must never be stated for all applicants. "
                        "During review, remove unasked details; retain only directly supported claims and their qualifiers.")
    return [
        {"role": "system", "content": instruction + "\nReturn ONLY JSON conforming to this schema:\n"
         + json.dumps(schema.model_json_schema(), ensure_ascii=False)},
        {"role": "user", "content": json.dumps(ordered, ensure_ascii=False)},
    ]


def evidence_spans(text):
    """Offer contiguous source spans; decoding cannot rewrite quoted numbers or labels."""
    spans = set()
    if 10 <= len(text) <= 1500:
        spans.add(text)
    # Keep offsets into the original text, including punctuation and whitespace.
    boundaries = [0] + [match.end() for match in re.finditer(r"\n|(?<=[.!?।])\s+", text)] + [len(text)]
    boundaries = sorted(set(boundaries))
    for start, end in zip(boundaries, boundaries[1:]):
        if end - start > 1500:
            # Extremely long source sentences remain unmodified contiguous spans.
            boundaries.extend(range(start + 1000, end, 1000))
    boundaries = sorted(set(boundaries))
    for index, start in enumerate(boundaries[:-1]):
        for end in boundaries[index + 1:index + 5]:
            value = text[start:end].strip()
            if 10 <= len(value) <= 1500:
                spans.add(value)
    return sorted(spans)


def generation_schema(schema, payload=None):
    """Keep grammar structural; validate numeric/string bounds with Pydantic afterward.

    Ollama's grammar compiler rejects some large bounded strings in these schemas.
    The full schema remains in the prompt and in post-generation validation.
    """
    bounds = {"minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems"}
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key not in bounds}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    result = clean(schema.model_json_schema())
    if schema.__name__ == "GroundedAnswer" and payload and payload.get("sources"):
        # A7 (FutureWork 05 §C): emit source_id + an integer span_index instead of a long
        # string enum of the quote itself. The index can only point at a real contiguous
        # span computed by evidence_spans, so fabricated or edited quotes are impossible,
        # and the token mask is over a small bounded int rather than hundreds of long
        # alternative strings (which made decode 2.6x slower). _invoke_local resolves each
        # index back to its exact span and populates the Evidence.quote field, so every
        # downstream grounding check (source_quote, citations, cache) is unchanged.
        choices = []
        for source in payload["sources"]:
            spans = evidence_spans(source["text"])
            if spans:
                choices.append({"type": "object", "properties": {
                    "source_id": {"const": source["source_id"]},
                    "span_index": {"type": "integer", "enum": list(range(len(spans)))}},
                    "required": ["source_id", "span_index"], "additionalProperties": False})
        if choices:
            result["$defs"]["Evidence"] = {"oneOf": choices}
    return result


def resolve_span_indices(payload, data):
    """Map each evidence {source_id, span_index} to its exact verbatim span.

    The grammar from generation_schema constrains the model to an integer index into
    evidence_spans(source["text"]); here we resolve it back to the quote string before
    Pydantic validation, so the rest of the pipeline sees an ordinary {source_id, quote}
    Evidence and the verbatim-quote guarantee is untouched. Out-of-range or unknown
    source_ids drop the item (fail closed); the node then treats missing evidence as
    an unverifiable answer. Non-grammar output (e.g. a draft that already carries a
    quote) is returned unchanged.
    """
    if not isinstance(data, dict) or not payload or not payload.get("sources"):
        return data
    spans_by_source = {source["source_id"]: evidence_spans(source["text"])
                       for source in payload["sources"]}
    resolved = []
    for item in data.get("evidence", []) or []:
        if not isinstance(item, dict) or "span_index" not in item:
            resolved.append(item)
            continue
        spans = spans_by_source.get(item.get("source_id"))
        index = item.get("span_index")
        if spans and isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(spans):
            resolved.append({"source_id": item["source_id"], "quote": spans[index]})
    data = dict(data)
    data["evidence"] = resolved
    return data


def prompt_tokens(schema, instruction, payload):
    # Count the exact model vocabulary, plus conservative room for chat-template tokens.
    tokenizer = _tokenizer(settings.OLLAMA_TOKENIZER_PATH)
    return 128 + sum(len(tokenizer.encode(m["content"], add_special_tokens=False).ids)
                     for m in _messages(schema, instruction, payload))


def prepare_payload(schema, instruction, payload, *, review_instruction=None, provider=None):
    """Budget before caching. Keep whole history pairs and whole evidence excerpts.

    Generation reserves a full output-sized draft for review. Review never drops evidence.
    The original payload and source IDs remain unchanged for callers.
    """
    if selected_provider(provider) != "ollama":
        return payload
    result = deepcopy(payload)
    def fits():
        # Count the exact prompt the local path will send: the GroundedAnswer answer call
        # augments sources with the A7 span menu, so budget against that augmented payload
        # (the review call and the cloud path are unaffected).
        used = prompt_tokens(schema, instruction, _local_grounding_payload(schema, result))
        if review_instruction is not None:
            used = max(used, prompt_tokens(schema, review_instruction, _local_grounding_payload(schema, result))
                       + settings.LLM_MAX_TOKENS + 128)
        return used + settings.LLM_MAX_TOKENS <= settings.OLLAMA_NUM_CTX
    while not fits() and result.get("history"):
        result["history"] = result["history"][2:]
    if review_instruction is not None:
        while not fits() and len(result.get("sources", [])) > 1:
            result["sources"].pop()
    if not fits():
        raise LocalModelError("This question and its evidence exceed the local context. Start a new conversation, "
                              "ask a narrower question, or explicitly select Groq.")
    return result


@lru_cache(maxsize=4)
def _local_client(base_url, timeout):
    return httpx.Client(base_url=base_url.rstrip("/") + "/", timeout=timeout, trust_env=False)


def _refresh_digest(client):
    """Fetch and cache the model digest from /api/tags (one localhost round-trip).

    The digest binds the draft-cache key (via model_identity), so replacing a local
    model under the same tag must invalidate earlier generated drafts. The digest
    changes only when someone re-pulls the model, so this is fetched lazily: once at
    process start (empty cache) and again whenever a call hits a 404 missing-model
    branch (the signal that the tag was removed or swapped). See FutureWork chapter 05 §D.
    """
    tags = client.get("api/tags", **({"timeout": operations.remaining(settings.OLLAMA_TIMEOUT_SECONDS)}
                                     if operations.current() else {}))
    tags.raise_for_status()
    digest = next((m["digest"] for m in tags.json()["models"] if m["name"] == settings.OLLAMA_MODEL), None)
    if not digest:
        raise LocalModelError("Local model is missing. Run ollama pull with the configured OLLAMA_MODEL.")
    _LOCAL_DIGESTS[(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)] = digest
    _refresh_thinking(client)


def _refresh_thinking(client):
    """Cache whether the model advertises the "thinking" capability (/api/show).

    Ollama returns HTTP 400 for a `think` field sent to a model that does not list
    `thinking` in its capabilities (e.g. a non-reasoning Qwen build), so _invoke_local
    must omit `think` for those models. Omitting it is output-equivalent to think:false
    on every model, so a probe that cannot determine the capability fails safe to
    "no thinking" (think omitted) rather than risking the 400. Fetched on the same lazy
    schedule as the digest (first use and after a 404)."""
    key = (settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)
    try:
        show = client.post("api/show", json={"model": settings.OLLAMA_MODEL},
                           **({"timeout": operations.remaining(settings.OLLAMA_TIMEOUT_SECONDS)}
                              if operations.current() else {}))
        show.raise_for_status()
        capabilities = show.json().get("capabilities") or []
        _LOCAL_THINKING[key] = "thinking" in capabilities
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        # Fail safe: if the capability cannot be read, do not send `think`.
        _LOCAL_THINKING[key] = False


def _local_grounding_payload(schema, payload):
    """Add a numbered span menu to each source so the local model can choose span_index.

    The grammar (generation_schema) constrains evidence to source_id + an integer index;
    the model needs to see which span each index denotes to choose faithfully. We expose
    the same evidence_spans list as `span_options` without touching `text`, so the grammar
    and resolve_span_indices (both keyed on `text`) stay byte-stable. Non-GroundedAnswer
    schemas and payloads without sources pass through unchanged.
    """
    if schema.__name__ != "GroundedAnswer" or not payload.get("sources"):
        return payload
    sources = []
    for source in payload["sources"]:
        spans = evidence_spans(source["text"])
        sources.append({**source, "span_options": dict(enumerate(spans))} if spans else dict(source))
    return {**payload, "sources": sources}


def _invoke_local(schema, instruction, payload):
    with _LOCAL_LOCK:
        operations.check()
        started, body, failure = time.monotonic(), {}, None
        try:
            client = _local_client(settings.OLLAMA_BASE_URL, settings.OLLAMA_TIMEOUT_SECONDS)
            # Skip the per-call /api/tags round-trip once the digest is cached; only a
            # re-pull changes it. Refresh on first use (empty cache) and after a 404.
            if (settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL) not in _LOCAL_DIGESTS:
                _refresh_digest(client)
            prompt_payload = _local_grounding_payload(schema, payload)
            body_json = {"model": settings.OLLAMA_MODEL,
                    "messages": _messages(schema, instruction, prompt_payload),
                    "format": generation_schema(schema, payload), "stream": False,
                    "keep_alive": settings.OLLAMA_KEEP_ALIVE,
                    "options": {"temperature": 0, "num_ctx": settings.OLLAMA_NUM_CTX,
                                "repeat_penalty": 1.0, "presence_penalty": 0,
                                "num_predict": settings.OLLAMA_NUM_PREDICT}}
            # Only send `think` to models that advertise the thinking capability; Ollama
            # rejects the field with HTTP 400 otherwise. Disabling thinking on a thinking
            # model needs think:false; omitting it entirely is equivalent for the rest.
            if _LOCAL_THINKING.get((settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)):
                body_json["think"] = False
            response = client.post("api/chat", json=body_json,
                **({"timeout": operations.remaining(settings.OLLAMA_TIMEOUT_SECONDS)}
                   if operations.current() else {}))
            if response.status_code == 404:
                # The tag was removed or swapped: drop the stale digest so the next call
                # re-fetches it (and rebinds the draft-cache identity) before reuse.
                _LOCAL_DIGESTS.pop((settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL), None)
                _LOCAL_THINKING.pop((settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL), None)
                raise LocalModelError("Local model is missing. Run ollama pull with the configured OLLAMA_MODEL.")
            response.raise_for_status()
            body = response.json()
            if not body.get("done") or body.get("done_reason") == "length":
                raise LocalModelError("The local response reached its output limit. Ask a narrower question or select Groq.")
            operations.check()
            # Resolve the grammar's integer span indices (A7) back to exact verbatim
            # quotes before validation, so callers receive an ordinary GroundedAnswer.
            return schema.model_validate(
                resolve_span_indices(payload, json.loads(body["message"]["content"])))
        except httpx.TimeoutException as error:
            failure = error
            raise LocalModelError("Local model timed out. Retry after loading finishes, or explicitly select Groq.") from error
        except httpx.ConnectError as error:
            failure = error
            raise LocalModelError("Cannot reach Ollama. Start ollama serve, then retry.") from error
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            failure = error
            raise LocalModelError("Local model returned an invalid response. Check Ollama and retry, or select Groq.") from error
        finally:
            operations.record_attempt("ollama", started, body, failure)


class RoutingDecision(BaseModel):
    """One classification call also resolves references and reminder details."""

    model_config = ConfigDict(extra="forbid")
    intent: Literal["knowledge", "smalltalk", "out_of_scope", "clarification", "handoff", "reminder", "cancel"]
    category: Literal["admissions", "hostel", "cg_counselling", "academics", "general"] = "general"
    language: Literal["english", "hindi", "hinglish"] = "english"
    query: str = Field(default="", max_length=2000, description=(
        "Standalone ENGLISH search question for the NEWEST message. A changed category, quota or round "
        "REPLACES its old value in the latest resolved_query; do not append conflicting old and new values. "
        "Never invent the topic of an unresolved pronoun when history is empty."))
    clarification: str = Field(default="", max_length=400)
    reminder_date: str = ""
    reminder_message: str = Field(default="", max_length=300)


class Evidence(BaseModel):
    """An exact source excerpt makes fabricated source references detectable.

    The local grammar constrains the model to pick span_index (an index into the
    numbered spans listed for each source); llm.resolve_span_indices replaces it with
    the exact verbatim quote before validation. The cloud path and the deterministic
    policy path populate quote directly. Either way the validated object always carries
    a verbatim quote, so evidence.source_quote and citations are unchanged.
    """

    model_config = ConfigDict(extra="forbid")
    source_id: int = Field(ge=1)
    quote: str = Field(min_length=10, max_length=1500, description=(
        "Copy one CONTIGUOUS verbatim span from this source's text. Preserve every word, label, "
        "punctuation mark and line order. Never combine separated lines, rewrite labels, paraphrase "
        "or translate. Use multiple evidence entries for separate spans."))


class GroundedAnswer(BaseModel):
    """Keep answerability and supporting evidence separate from spoken text."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["answered", "insufficient", "clarification"]
    answer: str = Field(min_length=1, max_length=2000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=8)
    clarification_field: Literal["", "programme", "year", "admission_category", "fee_type", "topic"] = ""


@lru_cache(maxsize=1)
def get_llm():
    """Reuse the provider client and bound latency for future call handling."""
    if not settings.GROQ_API_KEY:
        raise LocalModelError("Groq needs GROQ_API_KEY. Configure it or select Local.")
    return ChatGroq(
        model=settings.GROQ_CHAT_MODEL, api_key=settings.GROQ_API_KEY,
        temperature=0, timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=settings.LLM_MAX_RETRIES, max_tokens=settings.LLM_MAX_TOKENS,
    ).bind(response_format={"type": "json_object"})


def invoke_json(schema: type[BaseModel], instruction: str, payload: dict, *, provider=None):
    """Reject malformed JSON/schema output instead of guessing a model's intent."""
    operations.check()
    if selected_provider(provider) == "ollama":
        payload = prepare_payload(schema, instruction, payload, provider="ollama")
        return _invoke_local(schema, instruction, payload)
    raw = _messages(schema, instruction, payload)
    messages = [SystemMessage(content=raw[0]["content"]), HumanMessage(content=raw[1]["content"])]
    client = get_llm()
    def attempt():
        # Validate inside the attempt so a malformed-JSON response is retryable too,
        # not just transport errors. invoke_json has no side effects, so a retry can
        # never create a duplicate ticket, reminder or other action.
        operations.check()
        started, failure = time.monotonic(), None
        try:
            kwargs = {"timeout": operations.remaining(settings.LLM_TIMEOUT_SECONDS)} if operations.current() else {}
            response = client.invoke(messages, **kwargs)
            return schema.model_validate_json(response.content)
        except Exception as error:
            failure = error
            raise
        finally:
            operations.record_attempt("groq", started, error=failure)
    try:
        return attempt()
    except RateLimitError as error:
        # Retry only a provider-specified short pause. Never spin on a daily quota or
        # replay earlier graph nodes (which would waste tokens or repeat actions).
        delay = math.inf
        if error.response is not None:
            headers = error.response.headers
            for key in ("retry-after", "Retry-After", "x-ratelimit-reset-tokens"):
                raw = headers.get(key)
                if raw:
                    try:
                        delay = float(raw)
                        break
                    except (TypeError, ValueError):
                        pass
        # Fall back to a short default if no usable header found, to avoid giving
        # up immediately on transient bursts.
        if not math.isfinite(delay):
            delay = 5.0
        if not 0 < delay <= settings.LLM_RATE_LIMIT_MAX_WAIT_SECONDS:
            raise
        if operations.current():
            operations.remaining(delay)
            if delay >= operations.remaining(settings.LLM_RATE_LIMIT_MAX_WAIT_SECONDS + 1):
                raise operations.OperationStopped("deadline_exceeded")
            if operations.current().cancelled.wait(delay):
                raise operations.OperationStopped("cancelled")
        else:
            time.sleep(delay)
        return attempt()
    except ValidationError:
        # A 200 response whose JSON does not conform to the schema is a transient
        # formatting lapse, not an outage. Retry once (invoke_json has no side
        # effects) before surfacing an outage message. Transport and other errors
        # keep their existing no-retry contract and propagate unchanged.
        if operations.current():
            operations.check()
        return attempt()
