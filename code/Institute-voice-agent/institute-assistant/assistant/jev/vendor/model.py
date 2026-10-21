"""
jev, A single-file reference implementation of a "System One" decision model.

This is a from-first-principles reconstruction of the architecture described in
TypeSafe's Jev launch material. It is a *teaching* implementation: every piece is
written for legibility over speed, and it runs on CPU with random weights.

-------------------------------------------------------------------------------
THE CORE IDEA
-------------------------------------------------------------------------------
An LLM is a causal decoder that emits tokens one at a time. A System One model
deletes the decoder entirely and replaces it with:

    bidirectional state encoder  ->  typed read-out heads

Everything else follows from that one choice:

    * No output tokens, so output cost collapses to a single forward pass.
    * Type errors are impossible: the softmax support IS the declared option set.
    * Questions are answered in parallel, in isolation, against one shared state.
    * Adding questions barely moves latency (state encode dominates, O(T^2)).
    * Weak at System 2: compute per question is fixed, and there is no scratchpad.

-------------------------------------------------------------------------------
THE INFORMATION-FLOW ASYMMETRY (the important design decision)
-------------------------------------------------------------------------------
    questions  -> attend to -> state      YES
    state      -> attend to -> questions  NO
    questions  -> attend to -> questions  NO

The state is encoded ONCE, question-blind, and cached. Each question then rents
a few learned "slots" that cross-attend into that frozen representation.

    cost(state)    = O(T^2 * d)     <- dominates, paid once, cacheable
    cost(question) = O(M * T * d)   <- M is tiny (~8), so ~free

That asymmetry is what buys "no context rot" and "10 questions cost ~1 question".
The price is that the state representation cannot anticipate the question, which
is a real accuracy ceiling on long states with narrow questions.

-------------------------------------------------------------------------------
THE THREE PRIMITIVES
-------------------------------------------------------------------------------
    Noul    "Is this statement true?"      -> float in [0, 1]
    Choice  "Pick one of these K options"  -> option + distribution + confidence
    Score   "Rate on this ordinal rubric"  -> float + distribution + confidence

-------------------------------------------------------------------------------
PROBABILITY IS NOT CONFIDENCE
-------------------------------------------------------------------------------
    probability = aleatoric.  The state genuinely underdetermines the answer.
                  A 60/40 split can be exactly correct.
    confidence  = epistemic.  The model does not know: out of distribution,
                  malformed question, evidence simply absent from the state.

Collapsing these into max(probs) destroys the signal that makes unattended
automation viable. High-entropy-but-confident means "it really is 60/40, hedge".
Low confidence means "escalate to a human or a reasoning model".

Usage:
    python jev.py        # builds a tiny model, runs a mixed query, trains a step

Requires: torch >= 2.0
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field
from typing import Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


@dataclass(frozen=True)
class JevConfig:
    """Hyperparameters for the whole model.

    The default shape is deliberately lopsided: a wide-but-shallow state encoder
    and a *deep* read-out stack. Read-out layers operate on M~8 vectors instead
    of T~2000, so depth there is nearly free. That is where the real "thinking"
    budget goes.
    """

    vocab_size: int = 32_000
    d_model: int = 256
    n_heads: int = 8
    d_ff: int = 1024
    dropout: float = 0.1

    # State encoder (bidirectional, no causal mask).
    n_state_layers: int = 6
    max_state_len: int = 2048

    # Structure-aware positions: states are JSON/arrays, not prose.
    max_path_depth: int = 16
    max_sibling_index: int = 128
    path_hash_buckets: int = 4096

    # Question encoder (small, shared by questions and by option strings).
    n_question_layers: int = 2
    max_question_len: int = 64

    # Read-out stack.
    n_slots: int = 8
    n_readout_layers: int = 8

    # Score primitive: max number of ordinal rubric levels.
    max_score_levels: int = 16

    # Choice primitive: u8 cardinality cap, exactly as the docs describe.
    # Above this, real deployments run score-then-choose in two stages.
    max_options: int = 255

    def __post_init__(self) -> None:
        if self.d_model % self.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")


# These dataclasses ARE the type safety. A Choice question declares its options
# up front; the head builds a softmax whose support is exactly those options.
# There is no vocabulary to wander off into, so a schema violation is not
# "unlikely" -- it is unrepresentable.
@dataclass(frozen=True)
class Noul:
    """Is this statement true? Returns a single calibrated probability.

    Note there is no confidence field on the answer. For a binary, distance from
    0.5 already carries that information, and the primitive is meant to drop
    straight into an if-statement.
    """

    text: str
    key: str = ""


@dataclass(frozen=True)
class Choice:
    """Pick exactly one of `options`. Options are arbitrary runtime strings."""

    text: str
    options: Sequence[str]
    key: str = ""

    def __post_init__(self) -> None:
        if len(self.options) < 2:
            raise ValueError(f"Choice needs >= 2 options, got {len(self.options)}")
        if len(set(self.options)) != len(self.options):
            raise ValueError("Choice options must be unique")


@dataclass(frozen=True)
class Score:
    """Rate the state on an ordinal rubric.

    `labels` are ordered low -> high, e.g. ("calm", "frustrated", "very frustrated").
    Ordinality matters: confusing level 0 with level 3 is a worse error than
    confusing 0 with 1, and a flat softmax cannot express that.
    """

    text: str
    labels: Sequence[str]
    key: str = ""

    def __post_init__(self) -> None:
        if len(self.labels) < 2:
            raise ValueError(f"Score needs >= 2 levels, got {len(self.labels)}")


Question = Noul | Choice | Score


@dataclass(frozen=True)
class NoulAnswer:
    key: str
    noul: float  # P(statement is true), in [0, 1]


@dataclass(frozen=True)
class ChoiceAnswer:
    key: str
    choice: str  # argmax option; guaranteed to be one of the declared options
    probabilities: dict[str, float]
    confidence: float  # epistemic certainty, NOT max(probabilities)


@dataclass(frozen=True)
class ScoreAnswer:
    key: str
    score: float  # expected value over levels, e.g. 1.4
    probabilities: dict[str, float]
    confidence: float


Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer


# A real deployment uses a proper BPE tokenizer. This hash tokenizer exists so
# the file runs standalone. What matters here is `flatten_state`: it turns a
# nested JSON object into (token, path) pairs, which is how the model gets
# key-order invariance for free.
def stable_hash(text: str) -> int:
    """CRC32 of the utf-8 bytes.

    Python's built-in `hash()` for strings is randomized per process
    (PYTHONHASHSEED), which would make token ids and path ids differ between
    runs and silently break reproducibility. CRC32 is stable forever.
    """
    return zlib.crc32(text.encode("utf-8"))


class HashTokenizer:
    """Deterministic whitespace + hash tokenizer. A stand-in, not a real BPE."""

    PAD: int = 0

    def __init__(self, vocab_size: int) -> None:
        self.vocab_size = vocab_size

    def encode(self, text: str, max_len: int) -> list[int]:
        words = text.lower().replace(",", " ").replace(".", " ").split()
        ids = [1 + (stable_hash(w) % (self.vocab_size - 1)) for w in words[:max_len]]
        return ids or [1]

    def encode_batch(self, texts: Sequence[str], max_len: int) -> tuple[Tensor, Tensor]:
        """Returns (ids [B, L], pad_mask [B, L]) where pad_mask is True at PAD."""
        seqs = [self.encode(t, max_len) for t in texts]
        length = max(len(s) for s in seqs)
        ids = torch.full((len(seqs), length), self.PAD, dtype=torch.long)
        for i, s in enumerate(seqs):
            ids[i, : len(s)] = torch.tensor(s, dtype=torch.long)
        return ids, ids.eq(self.PAD)


StateValue = str | int | float | bool | None | dict | list


def flatten_state(
    state: StateValue,
    tokenizer: HashTokenizer,
    max_len: int,
    prefix: str = "",
    depth: int = 0,
    sibling: int = 0,
) -> tuple[list[int], list[tuple[int, int, int]]]:
    """Flatten nested JSON into token ids plus a structural path per token.

    Each token carries (depth, sibling_index, path_hash) instead of a flat
    position. Two consequences:

      1. Reordering dict keys does not change any token's positional encoding,
         so `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` encode identically. That is
         a large part of the consistency guarantee, enforced by construction
         rather than learned.
      2. The model can tell `customer.name` from `agent.name` even when the leaf
         text is identical.

    Returns:
        (token_ids, paths) where paths[i] = (depth, sibling, path_hash) for
        token i. Both are truncated to `max_len`.
    """
    ids: list[int] = []
    paths: list[tuple[int, int, int]] = []

    def emit(text: str, d: int, s: int, p: str) -> None:
        h = stable_hash(p)  # bucketed later, at the embedding table
        for tok in tokenizer.encode(text, max_len):
            if len(ids) >= max_len:
                return
            ids.append(tok)
            paths.append((d, s, h))

    if isinstance(state, dict):
        for i, (k, v) in enumerate(state.items()):
            child = f"{prefix}.{k}" if prefix else str(k)
            emit(str(k), depth, i, child)  # the key is content too
            sub_ids, sub_paths = flatten_state(
                v, tokenizer, max_len - len(ids), child, depth + 1, i
            )
            ids.extend(sub_ids)
            paths.extend(sub_paths)
    elif isinstance(state, (list, tuple)):
        for i, v in enumerate(state):
            child = f"{prefix}[{i}]"
            sub_ids, sub_paths = flatten_state(
                v, tokenizer, max_len - len(ids), child, depth + 1, i
            )
            ids.extend(sub_ids)
            paths.extend(sub_paths)
    else:
        emit(str(state), depth, sibling, prefix or "$")

    return ids[:max_len], paths[:max_len]


class FeedForward(nn.Module):
    """Standard pre-norm FFN with GELU."""

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(cfg.d_model)
        self.net = nn.Sequential(
            nn.Linear(cfg.d_model, cfg.d_ff),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(cfg.d_ff, cfg.d_model),
            nn.Dropout(cfg.dropout),
        )

    def forward(self, x: Tensor) -> Tensor:
        return x + self.net(self.norm(x))


class BidirectionalBlock(nn.Module):
    """Self-attention with NO causal mask.

    A causal decoder spends roughly half its attention capacity on a constraint
    (don't look right) that is pure overhead when you are not generating.
    Dropping it is close to a free doubling of comprehension per parameter, and
    it is the single cheapest win available to a non-generative model.
    """

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(cfg.d_model)
        self.attn = nn.MultiheadAttention(
            cfg.d_model, cfg.n_heads, dropout=cfg.dropout, batch_first=True
        )
        self.ffn = FeedForward(cfg)

    def forward(self, x: Tensor, pad_mask: Tensor | None = None) -> Tensor:
        """x: [B, L, d], pad_mask: [B, L] bool, True where padded."""
        h = self.norm(x)
        attended, _ = self.attn(h, h, h, key_padding_mask=pad_mask, need_weights=False)
        return self.ffn(x + attended)


class ReadoutBlock(nn.Module):
    """One layer of the read-out stack: slots read state, then talk among themselves.

    The self-attention here is WITHIN a single question's slots only. Slots
    belonging to different questions never meet, because questions are folded
    into the batch dimension before this runs. That is what guarantees question
    independence at the architecture level rather than by convention.
    """

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.cross_norm_q = nn.LayerNorm(cfg.d_model)
        self.cross_norm_kv = nn.LayerNorm(cfg.d_model)
        self.cross = nn.MultiheadAttention(
            cfg.d_model, cfg.n_heads, dropout=cfg.dropout, batch_first=True
        )
        self.self_norm = nn.LayerNorm(cfg.d_model)
        self.slot_attn = nn.MultiheadAttention(
            cfg.d_model, cfg.n_heads, dropout=cfg.dropout, batch_first=True
        )
        self.ffn = FeedForward(cfg)

    def forward(self, slots: Tensor, state: Tensor, pad_mask: Tensor | None) -> Tensor:
        """slots: [BN, M, d], state: [BN, T, d], pad_mask: [BN, T]."""
        kv = self.cross_norm_kv(state)
        read, _ = self.cross(
            self.cross_norm_q(slots),
            kv,
            kv,
            key_padding_mask=pad_mask,
            need_weights=False,
        )
        slots = slots + read

        h = self.self_norm(slots)
        mixed, _ = self.slot_attn(h, h, h, need_weights=False)
        return self.ffn(slots + mixed)


class StateEncoder(nn.Module):
    """Encodes the state once into [B, T, d]. Question-blind and cacheable.

    In production this is the whole latency story: O(T^2) and paid once per
    request. If you re-query the same state (a document, a policy, a session),
    you cache the KV and every subsequent query is microseconds.
    """

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.token = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=0)

        # Structural positions instead of (or alongside) flat ones.
        self.depth_emb = nn.Embedding(cfg.max_path_depth, cfg.d_model)
        self.sibling_emb = nn.Embedding(cfg.max_sibling_index, cfg.d_model)
        self.path_emb = nn.Embedding(cfg.path_hash_buckets, cfg.d_model)
        self.pos_emb = nn.Embedding(cfg.max_state_len, cfg.d_model)

        self.drop = nn.Dropout(cfg.dropout)
        self.layers = nn.ModuleList(
            BidirectionalBlock(cfg) for _ in range(cfg.n_state_layers)
        )
        self.norm = nn.LayerNorm(cfg.d_model)

    def forward(self, ids: Tensor, paths: Tensor, pad_mask: Tensor) -> Tensor:
        """ids: [B, T], paths: [B, T, 3], pad_mask: [B, T] -> [B, T, d]."""
        cfg = self.cfg
        B, T = ids.shape

        depth = paths[..., 0].clamp(0, cfg.max_path_depth - 1)
        sibling = paths[..., 1].clamp(0, cfg.max_sibling_index - 1)
        path_id = paths[..., 2].remainder(cfg.path_hash_buckets)
        flat = torch.arange(T, device=ids.device).clamp(max=cfg.max_state_len - 1)

        x = (
            self.token(ids)
            + self.depth_emb(depth)
            + self.sibling_emb(sibling)
            + self.path_emb(path_id)
            + self.pos_emb(flat).unsqueeze(0).expand(B, -1, -1)
        )
        x = self.drop(x)

        for layer in self.layers:
            x = layer(x, pad_mask)
        return self.norm(x)


class TextEncoder(nn.Module):
    """Small shared encoder for short strings: question text and option labels.

    Sharing weights between questions and options is what lets Choice handle
    arbitrary runtime option strings. Both land in the same space, so scoring is
    just a dot product.
    """

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.token = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=0)
        self.pos = nn.Embedding(cfg.max_question_len, cfg.d_model)
        self.layers = nn.ModuleList(
            BidirectionalBlock(cfg) for _ in range(cfg.n_question_layers)
        )
        self.norm = nn.LayerNorm(cfg.d_model)
        self.max_len = cfg.max_question_len

    def forward(self, ids: Tensor, pad_mask: Tensor) -> Tensor:
        """ids: [B, L] -> pooled [B, d] (mean over non-pad tokens)."""
        L = ids.shape[1]
        pos = torch.arange(L, device=ids.device).clamp(max=self.max_len - 1)
        x = self.token(ids) + self.pos(pos).unsqueeze(0)

        # A fully-padded row would make MultiheadAttention produce NaNs.
        safe_mask = pad_mask.clone()
        safe_mask[:, 0] = False

        for layer in self.layers:
            x = layer(x, safe_mask)
        x = self.norm(x)

        keep = (~safe_mask).unsqueeze(-1).to(x.dtype)
        return (x * keep).sum(1) / keep.sum(1).clamp(min=1.0)


class ConfidenceHead(nn.Module):
    """Epistemic confidence via evidential (Dirichlet) output.

    We predict a scalar "evidence" budget. Concentration alpha = 1 + evidence*p
    gives a Dirichlet whose total mass S encodes how much the model actually
    knows. Confidence is the complement of Dempster-Shafer vacuity:

        S = sum(alpha) = K + evidence
        confidence = 1 - K / S

    Zero evidence -> alpha is uniform ones -> confidence 0 -> "I have no idea,
    escalate". Crucially this is trained with a stop-gradient on the underlying
    probabilities, so the confidence objective can never distort the prediction
    it is describing.
    """

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(cfg.d_model),
            nn.Linear(cfg.d_model, cfg.d_model // 2),
            nn.GELU(),
            nn.Linear(cfg.d_model // 2, 1),
        )

    def forward(self, q: Tensor, n_classes: int) -> tuple[Tensor, Tensor]:
        """q: [B, d] -> (confidence [B], evidence [B])."""
        evidence = F.softplus(self.net(q).squeeze(-1))  # [B], >= 0
        total = n_classes + evidence
        return 1.0 - n_classes / total, evidence


class NoulHead(nn.Module):
    """Binary truth value. The sigmoid output IS the returned probability."""

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.proj = nn.Sequential(nn.LayerNorm(cfg.d_model), nn.Linear(cfg.d_model, 1))
        # Learned temperature: post-hoc calibration folded into the model.
        self.log_temp = nn.Parameter(torch.zeros(()))

    def forward(self, q: Tensor) -> Tensor:
        """q: [B, d] -> logits [B] (apply sigmoid for the probability)."""
        return self.proj(q).squeeze(-1) / self.log_temp.exp().clamp(min=1e-2)


class ChoiceHead(nn.Module):
    """Bi-encoder over runtime options. The softmax support is the option set.

    This is where "type errors are mathematically impossible" comes from. There
    is no vocabulary and no parsing step: we embed the K declared options, dot
    them against the read-out vector, and softmax over exactly those K. The
    model cannot return anything else because nothing else is representable.
    """

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.q_proj = nn.Sequential(
            nn.LayerNorm(cfg.d_model), nn.Linear(cfg.d_model, cfg.d_model)
        )
        self.o_proj = nn.Sequential(
            nn.LayerNorm(cfg.d_model), nn.Linear(cfg.d_model, cfg.d_model)
        )
        self.log_temp = nn.Parameter(torch.zeros(()))

    def forward(self, q: Tensor, options: Tensor, option_mask: Tensor) -> Tensor:
        """q: [B, d], options: [B, K, d], option_mask: [B, K] True where valid.

        Returns masked logits [B, K]; invalid slots are -inf so they receive
        exactly zero probability.
        """
        qv = self.q_proj(q).unsqueeze(1)  # [B, 1, d]
        ov = self.o_proj(options)  # [B, K, d]
        scale = math.sqrt(qv.shape[-1]) * self.log_temp.exp().clamp(min=1e-2)
        logits = (ov * qv).sum(-1) / scale  # [B, K]
        return logits.masked_fill(~option_mask, float("-inf"))


class ScoreHead(nn.Module):
    """Ordinal regression via CORAL: monotone cumulative thresholds.

    We predict P(score > k) for each threshold k, forced to be non-increasing in
    k by construction (thresholds descend via cumulative softplus). Level
    probabilities are the successive differences, and the reported score is the
    expectation, which is why you see values like 1.4 rather than a bare integer.

    Why not plain regression? Regression gives you a point with no distribution
    to branch on. Why not flat softmax? It treats level 0 vs 3 as no worse an
    error than 0 vs 1, discarding the rubric's ordering.
    """

    def __init__(self, cfg: JevConfig) -> None:
        super().__init__()
        self.max_levels = cfg.max_score_levels
        self.proj = nn.Sequential(nn.LayerNorm(cfg.d_model), nn.Linear(cfg.d_model, 1))
        self.bias0 = nn.Parameter(torch.zeros(()))
        # Positive deltas => strictly decreasing thresholds => monotone CDF.
        self.deltas = nn.Parameter(torch.zeros(cfg.max_score_levels - 2))
        self.log_temp = nn.Parameter(torch.zeros(()))

    def forward(self, q: Tensor, n_levels: int) -> Tensor:
        """q: [B, d] -> level probabilities [B, n_levels], summing to 1."""
        z = self.proj(q).squeeze(-1) / self.log_temp.exp().clamp(min=1e-2)  # [B]

        steps = F.softplus(self.deltas[: n_levels - 2])
        thresholds = self.bias0 - torch.cat(
            [torch.zeros(1, device=q.device), steps.cumsum(0)]
        )  # [n_levels - 1], strictly decreasing

        # cum[:, k] = P(score > k)
        cum = torch.sigmoid(z.unsqueeze(1) + thresholds.unsqueeze(0))  # [B, n_levels-1]

        ones = torch.ones(q.shape[0], 1, device=q.device)
        zeros = torch.zeros(q.shape[0], 1, device=q.device)
        upper = torch.cat([ones, cum], dim=1)  # P(score > k-1)
        lower = torch.cat([cum, zeros], dim=1)  # P(score > k)
        return (upper - lower).clamp(min=1e-8)  # [B, n_levels]


@dataclass
class StateCache:
    """An encoded state, ready to be queried repeatedly.

    This is the economic heart of the design. Encode a contract, a policy, or a
    support thread once; then ask fifty questions against it for almost nothing.
    """

    hidden: Tensor  # [B, T, d]
    pad_mask: Tensor  # [B, T]

    @property
    def batch_size(self) -> int:
        return self.hidden.shape[0]


class Jev(nn.Module):
    """A System One decision model: state in, typed probabilistic answers out.

    Forward pass:
        1. Encode the state once, bidirectionally.           O(T^2)
        2. Encode each question and its options.             O(N)
        3. Give each question M learned slots; cross-attend  O(N * M * T)
           into the frozen state through a deep read-out stack.
        4. Dispatch each slot bundle to its typed head.
    """

    def __init__(self, cfg: JevConfig, tokenizer: HashTokenizer | None = None) -> None:
        super().__init__()
        self.cfg = cfg
        self.tokenizer = tokenizer or HashTokenizer(cfg.vocab_size)

        self.state_encoder = StateEncoder(cfg)
        self.text_encoder = TextEncoder(cfg)

        # Learned slot initialization, conditioned on the question embedding.
        self.slot_init = nn.Parameter(torch.randn(cfg.n_slots, cfg.d_model) * 0.02)
        self.type_emb = nn.Embedding(3, cfg.d_model)  # noul / choice / score
        self.readout = nn.ModuleList(
            ReadoutBlock(cfg) for _ in range(cfg.n_readout_layers)
        )
        self.readout_norm = nn.LayerNorm(cfg.d_model)
        self.pool = nn.Linear(cfg.d_model * 2, cfg.d_model)  # mean + first slot

        self.noul_head = NoulHead(cfg)
        self.choice_head = ChoiceHead(cfg)
        self.score_head = ScoreHead(cfg)
        self.confidence_head = ConfidenceHead(cfg)

    def encode_state(self, states: Sequence[StateValue]) -> StateCache:
        """Encode a batch of JSON-like states. Cache and reuse this."""
        device = next(self.parameters()).device
        flat = [
            flatten_state(s, self.tokenizer, self.cfg.max_state_len) for s in states
        ]
        T = max(len(ids) for ids, _ in flat)

        ids = torch.zeros(len(flat), T, dtype=torch.long, device=device)
        paths = torch.zeros(len(flat), T, 3, dtype=torch.long, device=device)
        pad = torch.ones(len(flat), T, dtype=torch.bool, device=device)

        for i, (tok, pth) in enumerate(flat):
            n = len(tok)
            ids[i, :n] = torch.tensor(tok, dtype=torch.long, device=device)
            paths[i, :n] = torch.tensor(pth, dtype=torch.long, device=device)
            pad[i, :n] = False

        # An entirely-padded row makes MultiheadAttention softmax over nothing
        # and return NaN, which then silently poisons the whole batch. An empty
        # state is legal input, so keep one visible slot rather than crashing.
        pad[:, 0] = False

        hidden = self.state_encoder(ids, paths, pad)
        return StateCache(hidden=hidden, pad_mask=pad)

    def _readout(self, cache: StateCache, questions: Sequence[Question]) -> Tensor:
        """Run all questions against one state. Returns pooled vectors [B*N, d].

        Questions are folded into the batch dimension, which is precisely why
        they cannot interact: PyTorch's attention never crosses batch entries.
        Independence is structural, not a convention we hope holds.
        """
        device = next(self.parameters()).device
        B, N = cache.batch_size, len(questions)

        q_ids, q_pad = self.tokenizer.encode_batch(
            [q.text for q in questions], self.cfg.max_question_len
        )
        q_emb = self.text_encoder(q_ids.to(device), q_pad.to(device))  # [N, d]

        type_ids = torch.tensor(
            [{Noul: 0, Choice: 1, Score: 2}[type(q)] for q in questions], device=device
        )
        q_emb = q_emb + self.type_emb(type_ids)

        # [N, M, d] -> [B, N, M, d] -> [B*N, M, d]
        slots = self.slot_init.unsqueeze(0) + q_emb.unsqueeze(1)
        slots = (
            slots.unsqueeze(0)
            .expand(B, -1, -1, -1)
            .reshape(B * N, self.cfg.n_slots, -1)
        )

        # Each question sees the same state: [B, T, d] -> [B*N, T, d].
        T = cache.hidden.shape[1]
        state = cache.hidden.unsqueeze(1).expand(B, N, T, -1).reshape(B * N, T, -1)
        pad = cache.pad_mask.unsqueeze(1).expand(B, N, T).reshape(B * N, T)

        for layer in self.readout:
            slots = layer(slots, state, pad)
        slots = self.readout_norm(slots)

        return self.pool(torch.cat([slots.mean(1), slots[:, 0]], dim=-1))  # [B*N, d]

    def _encode_options(self, options: Sequence[str]) -> Tensor:
        device = next(self.parameters()).device
        ids, pad = self.tokenizer.encode_batch(list(options), self.cfg.max_question_len)
        return self.text_encoder(ids.to(device), pad.to(device))  # [K, d]

    def forward(
        self, states: Sequence[StateValue], questions: Sequence[Question]
    ) -> list[list[Answer]]:
        """Evaluate every question against every state.

        Returns answers[batch_index][question_index]. One forward pass total,
        regardless of how many questions you ask.
        """
        cache = self.encode_state(states)
        pooled = self._readout(cache, questions)  # [B*N, d]
        B, N = cache.batch_size, len(questions)

        results: list[list[Answer]] = [[] for _ in range(B)]
        for n, q in enumerate(questions):
            idx = torch.arange(B, device=pooled.device) * N + n
            vec = pooled[idx]  # [B, d]
            key = q.key or f"q{n}"

            if isinstance(q, Noul):
                probs = torch.sigmoid(self.noul_head(vec))
                for b in range(B):
                    results[b].append(NoulAnswer(key=key, noul=probs[b].item()))

            elif isinstance(q, Choice):
                opts = self._encode_options(q.options).unsqueeze(0).expand(B, -1, -1)
                mask = torch.ones(
                    B, len(q.options), dtype=torch.bool, device=vec.device
                )
                probs = F.softmax(self.choice_head(vec, opts, mask), dim=-1)
                conf, _ = self.confidence_head(vec, len(q.options))
                for b in range(B):
                    row = probs[b]
                    results[b].append(
                        ChoiceAnswer(
                            key=key,
                            choice=q.options[int(row.argmax())],
                            probabilities={
                                o: row[i].item() for i, o in enumerate(q.options)
                            },
                            confidence=conf[b].item(),
                        )
                    )

            else:  # Score
                probs = self.score_head(vec, len(q.labels))
                levels = torch.arange(
                    len(q.labels), dtype=probs.dtype, device=probs.device
                )
                expected = (probs * levels).sum(-1)
                conf, _ = self.confidence_head(vec, len(q.labels))
                for b in range(B):
                    row = probs[b]
                    results[b].append(
                        ScoreAnswer(
                            key=key,
                            score=expected[b].item(),
                            probabilities={
                                lbl: row[i].item() for i, lbl in enumerate(q.labels)
                            },
                            confidence=conf[b].item(),
                        )
                    )

        return results

    def logits(
        self, states: Sequence[StateValue], questions: Sequence[Question]
    ) -> list[tuple[Tensor, Tensor]]:
        """Differentiable path for training: list of (probs [B, K], confidence [B]).

        Noul returns K=2 as [P(false), P(true)] so all three primitives share one
        loss function.
        """
        cache = self.encode_state(states)
        pooled = self._readout(cache, questions)
        B, N = cache.batch_size, len(questions)

        out: list[tuple[Tensor, Tensor]] = []
        for n, q in enumerate(questions):
            idx = torch.arange(B, device=pooled.device) * N + n
            vec = pooled[idx]

            if isinstance(q, Noul):
                p_true = torch.sigmoid(self.noul_head(vec)).unsqueeze(-1)
                probs = torch.cat([1 - p_true, p_true], dim=-1)
            elif isinstance(q, Choice):
                opts = self._encode_options(q.options).unsqueeze(0).expand(B, -1, -1)
                mask = torch.ones(
                    B, len(q.options), dtype=torch.bool, device=vec.device
                )
                probs = F.softmax(self.choice_head(vec, opts, mask), dim=-1)
            else:
                probs = self.score_head(vec, len(q.labels))

            conf, _ = self.confidence_head(vec, probs.shape[-1])
            out.append((probs.clamp(min=1e-8), conf))
        return out


# The single most important rule: NEVER train on hard labels.
#
# Cross-entropy against a one-hot target manufactures overconfidence, which is
# exactly the failure this whole model exists to avoid. Instead, take soft
# targets from a frontier ensemble sampled across paraphrases, option orderings,
# and temperatures. If ten samples split 7/3, the target is 0.7.
#
# Ensemble disagreement is the calibration signal, and it is orders of magnitude
# cheaper to collect than real outcomes. (TypeSafe's own evals use "the average
# of GPT-6 Astra and Fable 5.1" as reference probabilities, which reads like an
# accidental disclosure of how the training targets are built.)
#
# The catch, worth being honest about: distillation caps you at the teacher, and
# inherits the teacher's biases. Real outcome data, where you have it, is what
# breaks that ceiling.
@dataclass
class RLCDLoss:
    """Composite objective for calibrated decisions.

        nll         proper scoring rule against SOFT targets
        brier       bounded, gradient-friendly, calibration-sensitive
        consistency KL between two augmentations of the same input
        evidential  trains confidence against ensemble disagreement
        ece         differentiable binned calibration penalty

    The consistency term is what actually delivers "similar inputs give similar
    outputs": paraphrase the state, shuffle JSON keys, permute option order, then
    penalize divergence. Cheap, and it directly kills position bias -- the
    failure mode where LLMs systematically prefer whichever option is listed first.
    """

    w_nll: float = 1.0
    w_brier: float = 0.5
    w_consistency: float = 0.5
    w_evidential: float = 0.2
    w_ece: float = 0.1
    n_ece_bins: int = 10
    parts: dict[str, float] = field(default_factory=dict)

    @staticmethod
    def soft_nll(probs: Tensor, target: Tensor) -> Tensor:
        """Cross-entropy against a soft target. probs/target: [B, K]."""
        return -(target * probs.clamp(min=1e-8).log()).sum(-1).mean()

    @staticmethod
    def brier(probs: Tensor, target: Tensor) -> Tensor:
        return ((probs - target) ** 2).sum(-1).mean()

    @staticmethod
    def symmetric_kl(p: Tensor, q: Tensor) -> Tensor:
        p, q = p.clamp(min=1e-8), q.clamp(min=1e-8)
        return 0.5 * ((p * (p / q).log()).sum(-1) + (q * (q / p).log()).sum(-1)).mean()

    @staticmethod
    def evidential(conf: Tensor, probs: Tensor, target: Tensor) -> Tensor:
        """Train confidence toward agreement with the target distribution.

        The stop-gradient is load-bearing. Without it, the model could lower its
        confidence loss by making its predictions blander, and the confidence
        objective would start corrupting the thing it is meant to describe.
        """
        with torch.no_grad():
            agreement = (probs.detach() * target).sum(-1)  # in [0, 1]
        return F.mse_loss(conf, agreement)

    def ece(self, probs: Tensor, target: Tensor) -> Tensor:
        """Differentiable soft-binned |confidence - accuracy| gap."""
        conf, idx = probs.max(-1)
        acc = target.gather(-1, idx.unsqueeze(-1)).squeeze(-1)
        total = probs.new_zeros(())
        for b in range(self.n_ece_bins):
            lo, hi = b / self.n_ece_bins, (b + 1) / self.n_ece_bins
            w = ((conf >= lo) & (conf < hi)).to(probs.dtype)
            if w.sum() > 0:
                total = total + w.mean() * ((w * (conf - acc)).sum() / w.sum()).abs()
        return total

    def __call__(
        self,
        model: Jev,
        states: Sequence[StateValue],
        questions: Sequence[Question],
        targets: Sequence[Tensor],
        augmented_states: Sequence[StateValue] | None = None,
    ) -> Tensor:
        """One training step.

        Args:
            targets: one [B, K] soft-target tensor per question, rows summing
                to 1. These are teacher-ensemble frequencies, not one-hots.
            augmented_states: semantically identical restatements of `states`
                (shuffled keys, paraphrases). Enables the consistency term.
        """
        preds = model.logits(states, questions)
        aug = model.logits(augmented_states, questions) if augmented_states else None

        nll = brier = ev = ece = cons = torch.zeros((), device=preds[0][0].device)

        for i, (probs, conf) in enumerate(preds):
            tgt = targets[i].to(probs.device)
            nll = nll + self.soft_nll(probs, tgt)
            brier = brier + self.brier(probs, tgt)
            ev = ev + self.evidential(conf, probs, tgt)
            ece = ece + self.ece(probs, tgt)
            if aug is not None:
                cons = cons + self.symmetric_kl(probs, aug[i][0])

        n = len(preds)
        nll, brier, ev, ece, cons = (t / n for t in (nll, brier, ev, ece, cons))

        total = (
            self.w_nll * nll
            + self.w_brier * brier
            + self.w_evidential * ev
            + self.w_ece * ece
            + self.w_consistency * cons
        )
        self.parts = {
            "nll": nll.item(),
            "brier": brier.item(),
            "evidential": ev.item(),
            "ece": ece.item(),
            "consistency": cons.item(),
            "total": total.item(),
        }
        return total
