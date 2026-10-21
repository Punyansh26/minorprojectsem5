"""Versioned routing vocabulary, artifact helpers and operational acceptance policy."""
from hashlib import sha256
import json
import math
from pathlib import Path
import re

VERSION = 1
UPSTREAM = "93843ef288f3d35fd91263377c40b6f917d77da0"
INTENTS = ("knowledge", "smalltalk", "out_of_scope", "clarification", "handoff", "reminder", "cancel")
CATEGORIES = ("admissions", "hostel", "cg_counselling", "academics", "general")
LANGUAGES = ("english", "hindi", "hinglish", "unsupported")
LABELS = (INTENTS, CATEGORIES, LANGUAGES, (False, True))
SAFE_INTENTS = {"knowledge", "smalltalk", "out_of_scope", "clarification"}
INSTITUTE = re.compile(r"\b(?:IIIT[\s-]*NR|IIIT\s+Naya\s+Raipur)\b", re.I)
ACTION = re.compile(r"\b(?:remind|reminder|schedule|cancel|staff|handoff|escalat\w*|ticket|contact|email|human|forget|yaad|bhej|adhikari|radd)\b|याद|रिमाइंड|रद्द|भेज|अधिकारी|शिकायत", re.I)


def digest(path):
    h = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def questions():
    from .vendor.model import Choice, Noul
    return [Choice("What is the helpdesk intent?", INTENTS, "intent"),
            Choice("Which college department category applies?", CATEGORIES, "category"),
            Choice("What is the message language?", LANGUAGES, "language"),
            Noul("Does this message need translation, reference resolution, or removal of an unrelated request before searching?", "rewrite")]


def preflight(message, history=(), pending=None, max_chars=2000):
    if not message.strip() or len(message) > max_chars:
        return "input_size"
    if pending:
        return "pending_action"
    if history:
        return "conversation_history"
    if ACTION.search(message):
        return "action_language"
    from .english_policy import non_english_hint
    if non_english_hint(message):
        return "non_english"
    return None


def accepted(message, prediction, thresholds):
    """Return a RoutingDecision only when every required head passes validation."""
    from .english_policy import non_english_hint, route
    if thresholds.get("policy") == "english-v2":
        return route(message, prediction, thresholds)[0]
    from assistant.llm import RoutingDecision
    if (prediction["intent"] not in SAFE_INTENTS or prediction["language"] != "english"
            or non_english_hint(message)):
        return None
    for name in ("intent", "category", "language"):
        if not math.isfinite(prediction[name + "_probability"]) or not 0 <= prediction[name + "_probability"] <= 1 or not math.isfinite(prediction[name + "_confidence"]) or not 0 <= prediction[name + "_confidence"] <= 1:
            return None
        if prediction[name + "_probability"] < thresholds["probability"] or prediction[name + "_confidence"] < thresholds["confidence"]:
            return None
    if prediction["intent"] == "knowledge":
        if (prediction["language"] != "english" or not INSTITUTE.search(message)
                or re.search(r"[\u0900-\u097f]", message)
                or not math.isfinite(prediction["rewrite_probability"])
                or prediction["rewrite_probability"] > thresholds["rewrite"]):
            return None
    return RoutingDecision(intent=prediction["intent"], category=prediction["category"],
                           language=prediction["language"],
                           query=message if prediction["intent"] == "knowledge" else "")


def prediction_rows(outputs):
    """Convert differentiable heads to serializable probabilities without trusting labels."""
    rows = []
    for i in range(outputs[0][0].shape[0]):
        row = {}
        for n, name in enumerate(("intent", "category", "language")):
            probs, confidence = outputs[n]
            values = probs[i].detach().cpu().tolist()
            if (any(not math.isfinite(p) or not 0 <= p <= 1 for p in values)
                    or abs(sum(values) - 1) > 1e-4):
                raise ValueError("Invalid model distribution")
            idx = max(range(len(values)), key=values.__getitem__)
            row.update({name: LABELS[n][idx], name + "_probability": values[idx],
                        name + "_confidence": float(confidence[i].detach().cpu()), name + "_distribution": values})
        row["rewrite_probability"] = float(outputs[3][0][i, 1].detach().cpu())
        rows.append(row)
    return rows


class BPETokenizer:
    """Upstream tokenizer protocol with stable PAD=0 and byte-level Unicode coverage."""
    PAD = 0

    def __init__(self, path):
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(path))
        if self.tokenizer.token_to_id("[PAD]") != 0:
            raise ValueError("Tokenizer padding mismatch")

    def encode(self, text, max_len):
        return self.tokenizer.encode(text).ids[:max_len] or [1]

    def encode_batch(self, texts, max_len):
        import torch
        seqs = [self.encode(text, max_len) for text in texts]
        ids = torch.zeros((len(seqs), max(map(len, seqs))), dtype=torch.long)
        for i, seq in enumerate(seqs):
            ids[i, :len(seq)] = torch.tensor(seq)
        return ids, ids.eq(0)


def normalized_message(message):
    return " ".join(message.casefold().split()).rstrip("?.!।")


def live_case_overlaps(rows):
    """Identify existing live cases exposed in training/calibration, including variants' bases."""
    from evaluate_helpdesk import CASES
    exposed = {normalized_message(r["message"]) for r in rows if r["split"] != "test"}
    return {name for name, messages, _ in CASES if any(normalized_message(q) in exposed for q in messages)}
