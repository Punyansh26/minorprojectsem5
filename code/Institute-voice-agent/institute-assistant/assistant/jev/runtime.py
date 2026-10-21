"""Fail-to-existing-router inference in one bounded CPU worker process."""
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
from functools import lru_cache
import math
import multiprocessing
from pathlib import Path
from threading import Lock, Semaphore
from time import perf_counter

from .common import (BPETokenizer, LABELS, UPSTREAM, VERSION, accepted, digest,
                     json_hash, prediction_rows, preflight, questions, read_json)

_POOL = None
_POOL_LOCK = Lock()
_CAPACITY = Semaphore(1)
ENGLISH_BACKENDS = {"minilm-english-v2", "minilm-english-v3"}


def artifact_signature(root):
    root = Path(root).resolve()
    manifest = read_json(root / "manifest.json")
    if manifest.get("backend") in ENGLISH_BACKENDS:
        names = set(manifest["files"]) | {"manifest.json"}
        encoder = (root / manifest["encoder_dir"]).resolve()
        if not encoder.is_relative_to(root):
            raise ValueError("Invalid encoder path")
        names.update(str(p.relative_to(root)) for p in encoder.rglob("*") if p.is_file())
        if any(not (root / name).resolve().is_relative_to(root) for name in names):
            raise ValueError("Invalid artifact path")
        return tuple((name, (root / name).stat().st_mtime_ns, (root / name).stat().st_size)
                     for name in sorted(names))
    return tuple((name, (Path(root) / name).stat().st_mtime_ns, (Path(root) / name).stat().st_size)
                 for name in ("manifest.json", "model.pt", "tokenizer.json"))


@lru_cache(maxsize=2)
def checked_manifest(root, signature):
    manifest = read_json(Path(root) / "manifest.json")
    if manifest.get("backend") == "minilm-english-v3":
        from .english_v3_training import checked_manifest as check_v3
        return check_v3(root, manifest)
    if manifest.get("backend") == "minilm-english-v2":
        from .english_training import checked_manifest as check_english
        from .english_normalization import check_normalization
        check_normalization(manifest)
        return check_english(root, manifest)
    if (manifest["version"] != VERSION or manifest["upstream"] != UPSTREAM
            or json_hash(manifest["labels"]) != json_hash(LABELS)
            or manifest["training_examples"] < 64 or manifest["epochs"] < 1):
        raise ValueError("Incompatible or untrained artifact")
    if any(digest(Path(root) / name) != manifest[field] for name, field in
           (("model.pt", "model_sha256"), ("tokenizer.json", "tokenizer_sha256"))):
        raise ValueError("Artifact checksum mismatch")
    thresholds = manifest["thresholds"]
    if set(thresholds) != {"probability", "confidence", "rewrite"} or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1
            for x in thresholds.values()):
        raise ValueError("Invalid calibrated thresholds")
    if manifest["config"]["max_state_len"] != 512 or manifest["config"]["vocab_size"] != 8192:
        raise ValueError("Incompatible model shape")
    return manifest


def activation_valid(root, manifest):
    """Certificate binds passing reports and exact model/tokenizer/thresholds."""
    from .evaluation import quality_passed, benchmark_passed
    root = Path(root)
    if not all((root/name).is_file() for name in ("activation.json","evaluation.json","benchmark.json")):
        return False
    activation = read_json(root / "activation.json")
    evaluation = read_json(root / "evaluation.json")
    benchmark = read_json(root / "benchmark.json")
    if manifest.get("backend") == "minilm-english-v3" and benchmark.get("benchmark_version") != 2:
        return False
    if manifest.get("backend") in ENGLISH_BACKENDS and not (
            manifest["thresholds"]["supported"] and evaluation.get("evaluation_kind") == "final_holdout"
            and evaluation.get("independent_human_review") is True):
        return False
    identity = json_hash(manifest)
    return (activation["artifact_id"] == identity == evaluation["artifact_id"] == benchmark["artifact_id"]
            and activation["evaluation_sha256"] == digest(root / "evaluation.json")
            and activation["benchmark_sha256"] == digest(root / "benchmark.json")
            and quality_passed(evaluation) and benchmark_passed(benchmark))


@lru_cache(maxsize=2)
def _worker_model(root, signature, threads):
    import torch
    from .vendor.model import Jev, JevConfig
    manifest = checked_manifest(root, signature)
    torch.set_num_threads(threads)  # Isolated worker; never changes speech/embedding threads.
    if manifest.get("backend") == "minilm-english-v3":
        from .english_v3_model import load_router
        return load_router(root, manifest)
    if manifest.get("backend") == "minilm-english-v2":
        from .english_normalization import load_inference_router
        return load_inference_router(root, manifest)
    tokenizer = BPETokenizer(Path(root) / "tokenizer.json")
    model = Jev(JevConfig(**manifest["config"]), tokenizer)
    model.load_state_dict(torch.load(Path(root) / "model.pt", map_location="cpu", weights_only=True), strict=True)
    model.eval()
    return model


def _worker_predict(root, signature, threads, message):
    import torch
    model = _worker_model(root, signature, threads)
    manifest = checked_manifest(root, signature)
    if manifest.get("backend") in ENGLISH_BACKENDS:
        if manifest["backend"] == "minilm-english-v3":
            from .english_v3_model import predictions
        else:
            from .english_model import predictions
        if model.token_lengths([message])[0] > manifest["max_tokens"]:
            return None
        with torch.inference_mode():
            return predictions(model([message]), manifest["temperatures"])[0]
    if len(model.tokenizer.tokenizer.encode(message).ids) > model.cfg.max_state_len:
        return None
    with torch.inference_mode():
        return prediction_rows(model.logits([message], questions()))[0]


def predict(root, signature, threads, timeout, message):
    global _POOL
    if not _CAPACITY.acquire(blocking=False):
        return None, "busy"
    future = None
    try:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
            future = _POOL.submit(_worker_predict, root, signature, threads, message)
        # Hold capacity until the real work ends, including after a caller timeout.
        future.add_done_callback(lambda _: _CAPACITY.release())
        result = future.result(timeout=timeout)
        return result, "token_limit" if result is None else None
    except Exception as error:
        if isinstance(error, BrokenProcessPool):
            with _POOL_LOCK:
                if _POOL is not None:
                    _POOL.shutdown(wait=False, cancel_futures=True)
                    _POOL = None
        if future is None:
            _CAPACITY.release()
        return None, "timeout" if isinstance(error,TimeoutError) else "inference_error"


def _laya_preflight(message, pending, max_chars):
    """Bilingual preflight: keep Hindi/Hinglish, but hold action and size boundaries.

    Unlike `common.preflight`, this does NOT reject non-English text, because the Laya
    multilingual checkpoint handles Hindi. It still refuses empty/oversized input,
    pending actions, and messages that look like an action/reminder request, since
    those must reach the full graph rather than a fast local route.
    """
    from .common import ACTION
    if not message.strip() or len(message) > max_chars:
        return "input_size"
    if pending:
        return "pending_action"
    if ACTION.search(message):
        return "action_language"
    return None


def _try_laya(message, history, pending, settings, metrics):
    """Route via a local laya-serve (HTTP) instead of a trained artifact or an LLM.

    No model loads in this process and no artifact/activation is required: Laya is a
    published, zero-shot checkpoint served out-of-process. Correctness is protected by
    the shared confidence/institute gates in `laya_adapter.laya_route`; only confident,
    safe, institute-grounded (for knowledge) routes short-circuit the LLM.
    """
    from .laya_adapter import LayaUnavailable, laya_route, request_prediction
    metrics["router_backend"] = "laya"
    # History is not sent to Laya; a follow-up that depends on prior turns must use
    # the LLM router, which sees the conversation.
    if history:
        metrics["router_fallback"] = "conversation_history"
        return None
    reason = _laya_preflight(message, pending, settings.MAX_QUESTION_CHARS)
    if reason:
        metrics["router_fallback"] = reason
        return None
    thresholds = {"probability": settings.LAYA_PROBABILITY_THRESHOLD,
                  "confidence": settings.LAYA_CONFIDENCE_THRESHOLD,
                  "rewrite": settings.LAYA_REWRITE_THRESHOLD}
    started = perf_counter()
    try:
        metrics["classifier_calls"] = 1
        prediction = request_prediction(settings.LAYA_BASE_URL, message, settings.JEV_TIMEOUT_SECONDS)
        decision, rejection = laya_route(message, prediction, thresholds)
        metrics["router_path"] = "laya" if decision else "llm"
        metrics["router_fallback"] = None if decision else rejection
        return decision
    except LayaUnavailable:
        # laya-serve down or unreachable: fail safe to the existing LLM router.
        metrics["router_fallback"] = "laya_unavailable"
        return None
    except Exception:
        metrics["router_fallback"] = "laya_error"
        return None
    finally:
        metrics.setdefault("stage_ms", {})["classifier"] = round((perf_counter() - started) * 1000, 3)


def try_route(message, history, pending, settings, metrics):
    """Only enabled + certified artifacts may replace a routing LLM call."""
    mode = settings.JEV_ROUTING_MODE
    metrics.update({"router_path": "llm", "router_mode": mode, "classifier_calls": 0,
                    "router_version": None, "router_fallback": None})
    if mode == "off":
        metrics["router_fallback"] = "disabled"
        return None
    if mode == "laya":
        return _try_laya(message, history, pending, settings, metrics)
    # Common cheap exclusions run before loading any assets. History is checked by
    # the selected version; v3 also supports bounded English follow-ups.
    reason = preflight(message, (), pending, settings.MAX_QUESTION_CHARS)
    if reason:
        metrics["router_fallback"] = reason
        return None
    started = perf_counter()
    try:
        root = str(Path(settings.JEV_ARTIFACT_DIR).expanduser().resolve())
        signature = artifact_signature(root)
        manifest = checked_manifest(root, signature)
        v3 = manifest.get("backend") == "minilm-english-v3"
        if history and not v3:
            metrics["router_fallback"] = "conversation_history"
            return None
        metrics["router_version"] = json_hash(manifest)[:16]
        if mode == "enabled" and not activation_valid(root, manifest):
            metrics["router_fallback"] = "not_activated"
            return None
        if v3 and manifest["thresholds"]["supported"]:
            from .english_v3_policy import exact_followup
            exact = exact_followup(message, history, pending)
            if exact:
                metrics["query_strategy"] = exact.query_strategy
                if mode == "shadow":
                    metrics.update(router_path="shadow", router_fallback="shadow",
                                   router_shadow_intent="knowledge")
                    return None
                metrics.update(router_path="deterministic_followup", category_abstained=True)
                return exact
        metrics["classifier_calls"] = 1
        prediction, failure = predict(root, signature, settings.JEV_CPU_THREADS,
                                      settings.JEV_TIMEOUT_SECONDS, message)
        if failure:
            metrics["router_fallback"] = failure
            return None
        rejection = "uncertain_or_ineligible"
        if v3:
            from .english_v3_policy import route
            decision, rejection = route(message, prediction, manifest["thresholds"], history, pending)
            if decision:
                metrics["query_strategy"] = decision.query_strategy
                metrics["category_abstained"] = decision.retrieval_preference is None
        elif manifest.get("backend") == "minilm-english-v2":
            from .english_policy import route
            decision, rejection = route(message, prediction, manifest["thresholds"])
        else:
            decision = accepted(message, prediction, manifest["thresholds"])
        if mode == "shadow":
            metrics["router_path"] = "shadow"
            metrics["router_shadow_intent"] = (decision.decision.intent if v3 else decision.intent) if decision else None
            metrics["router_fallback"] = "shadow" if decision else rejection
            return None
        metrics["router_path"] = "open_jev" if decision else "llm"
        metrics["router_fallback"] = None if decision else rejection
        return decision
    except FileNotFoundError:
        metrics["router_fallback"] = "artifact_missing"
        return None
    except (ValueError,KeyError,TypeError):
        metrics["router_fallback"] = "artifact_corrupt"
        return None
    except Exception:
        # No exception bodies or user input in logs/metrics.
        metrics["router_fallback"] = "artifact_error"
        return None
    finally:
        metrics.setdefault("stage_ms", {})["classifier"] = round((perf_counter() - started) * 1000, 3)
