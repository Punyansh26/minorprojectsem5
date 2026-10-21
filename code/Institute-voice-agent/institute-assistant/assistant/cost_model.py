"""Reproducible latency, memory and cost equations from FutureWork chapter 02.

Every planning number in the roadmap (chapter 13) is [Estimated] from these
equations and the measured baseline (chapter 01). This module turns those
equations into pure, side-effect-free functions so a reviewer can re-derive any
figure instead of trusting a hand calculation. Nothing here does I/O, loads a
model, or reads the network; the live token counts come from
``metrics.call_model`` (see ``split_call_rates``) and are fed in as arguments.

Symbols follow chapter 02 §9. Durations are seconds and rates are tokens/second
unless a name says otherwise. Memory is mebibytes (MiB) unless a name says GB.

Evidence labels (chapter 00):
  [Measured-here] taken on the project laptop (T0) on 2026-10-05.
  [Reported]      cited from a source, not reproduced.
  [Estimated]     derived here; replace with a measurement when one exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --- Measured baseline constants (T0, qwen3.5:9b Q4_K_M) [Measured-here, 01 §4.3] ---

R_PREFILL_TOK_S = 820.0      # prefill throughput, 920-token cold prompt
R_DECODE_TOK_S = 17.7        # free-text decode throughput (10 tokens in 565 ms)
R_DECODE_ENUM_TOK_S = 6.4    # decode under a ~300-entry string-enum grammar
COLD_LOAD_SECONDS = 8.3      # cold model load; 0 when resident
GRAMMAR_PENALTY = R_DECODE_TOK_S / R_DECODE_ENUM_TOK_S  # ≈2.6x slower [Measured-here]

# Answered-turn medians, baseline run (01 §4.1) [Measured-here], seconds.
BASELINE_ROUTING_S = 3.80
BASELINE_GENERATION_S = 7.18
BASELINE_REVIEW_S = 7.41
BASELINE_RETRIEVAL_S = 0.050
BASELINE_ANSWERED_TURN_S = 18.7

# Memory-bound decode model (01 §4.3 / 02 §2.1). Bandwidths are vendor peaks;
# EFFICIENCY is an assumption to be replaced by measurement [Estimated].
WEIGHTS_GB_Q4 = 5.6          # 9.7B params x ~4.8 bit
GPU_PEAK_BW_GB_S = 256.0     # RTX 4060 Laptop
CPU_PEAK_BW_GB_S = 85.7      # ~60 GB/s effective assumed in the chapter -> peak/0.7
EFFICIENCY = 0.70            # effective fraction of peak bandwidth [Estimated]

IDLE_GPU_WATTS = 16.8        # only idle power was read for the report [Measured-here]


# --- §1 Perceived latency -------------------------------------------------

@dataclass(frozen=True)
class PerceivedLatency:
    """T_perceived = EOU + ASR residual + LLM TTFT + TTS TTFB + transport (02 §1)."""

    t_eou: float = 0.0
    t_asr_residual: float = 0.0
    t_llm_ttft: float = 0.0
    t_tts_ttfb: float = 0.0
    t_transport: float = 0.0

    @property
    def total(self) -> float:
        return (self.t_eou + self.t_asr_residual + self.t_llm_ttft
                + self.t_tts_ttfb + self.t_transport)


def perceived_latency(**terms: float) -> float:
    """Sum of the perceived-latency terms. Unknown terms default to 0."""
    return PerceivedLatency(**terms).total


def streaming_first_output(first_chunk_latencies) -> float:
    """§1.1 streaming time to first output: sum of each stage's first-chunk latency."""
    return float(sum(first_chunk_latencies))


# --- §2 One LLM call ------------------------------------------------------

def llm_call_seconds(n_prompt: int, n_out: int, *, n_reused: int = 0,
                     r_prefill: float = R_PREFILL_TOK_S, r_decode: float = R_DECODE_TOK_S,
                     t_load: float = 0.0, t_overhead: float = 0.0) -> float:
    """t_call = t_load + t_overhead + (N_prompt - N_reused)/r_prefill + N_out/r_decode."""
    if n_prompt < 0 or n_out < 0 or n_reused < 0:
        raise ValueError("token counts must be non-negative")
    if r_prefill <= 0 or r_decode <= 0:
        raise ValueError("rates must be positive")
    prefill_tokens = max(0, n_prompt - n_reused)
    return t_load + t_overhead + prefill_tokens / r_prefill + n_out / r_decode


def decode_bound_output_threshold(n_prompt: int, *, r_prefill: float = R_PREFILL_TOK_S,
                                  r_decode: float = R_DECODE_TOK_S) -> float:
    """§2 output tokens above which decode dominates: N_out > N_prompt * r_decode/r_prefill."""
    return n_prompt * (r_decode / r_prefill)


def is_decode_bound(n_prompt: int, n_out: int, *, r_prefill: float = R_PREFILL_TOK_S,
                    r_decode: float = R_DECODE_TOK_S) -> bool:
    return n_out > decode_bound_output_threshold(n_prompt, r_prefill=r_prefill, r_decode=r_decode)


# --- §2.1 Memory-bound decode --------------------------------------------

def decode_tokens_per_second(b_gpu_gb: float, b_cpu_gb: float, *,
                             bw_gpu_gb_s: float = GPU_PEAK_BW_GB_S,
                             bw_cpu_gb_s: float = CPU_PEAK_BW_GB_S,
                             efficiency: float = EFFICIENCY) -> float:
    """§2.1 t_token ≈ B_gpu/BW_gpu + B_cpu/BW_cpu; return 1/t_token (tok/s).

    Bandwidths are vendor peaks scaled by ``efficiency``. With everything on the
    GPU set ``b_cpu_gb=0``.
    """
    if b_gpu_gb < 0 or b_cpu_gb < 0:
        raise ValueError("resident bytes must be non-negative")
    eff_gpu = bw_gpu_gb_s * efficiency
    eff_cpu = bw_cpu_gb_s * efficiency
    t_token = (b_gpu_gb / eff_gpu if b_gpu_gb else 0.0) + (b_cpu_gb / eff_cpu if b_cpu_gb else 0.0)
    if t_token <= 0:
        raise ValueError("at least one device must hold weights")
    return 1.0 / t_token


def split_weights_gb(cpu_fraction: float, total_gb: float = WEIGHTS_GB_Q4) -> tuple[float, float]:
    """Return (B_gpu_gb, B_cpu_gb) for a CPU offload fraction in [0, 1]."""
    if not 0.0 <= cpu_fraction <= 1.0:
        raise ValueError("cpu_fraction must be between 0 and 1")
    b_cpu = total_gb * cpu_fraction
    return total_gb - b_cpu, b_cpu


# --- §3 Memory: will it fit? ---------------------------------------------

def kv_cache_mib(n_ctx: int, *, attn_layers: int = 8, kv_heads: int = 4,
                 head_dim: int = 256, bytes_per_elem: int = 2) -> float:
    """Standard-attention KV cache: 2 * L_attn * H_kv * d_head * n_ctx * b (02 §3).

    Qwen3.5-9B is hybrid: only 8 of 32 layers are full attention. Default args
    reproduce the chapter's 256 MiB figure at n_ctx=8192, f16.
    """
    if n_ctx <= 0:
        raise ValueError("n_ctx must be positive")
    return 2 * attn_layers * kv_heads * head_dim * n_ctx * bytes_per_elem / (1024 ** 2)


def vram_fits(m_weights_mib: float, m_kv_mib: float, m_state_mib: float,
              m_compute_mib: float, m_other_mib: float, m_gpu_mib: float) -> bool:
    """§3: sum of VRAM terms must not exceed the GPU's capacity."""
    total = m_weights_mib + m_kv_mib + m_state_mib + m_compute_mib + m_other_mib
    return total <= m_gpu_mib


# --- §4 Amdahl's law ------------------------------------------------------

def amdahl_speedup(p: float, s: float) -> float:
    """S_turn = 1 / ((1 - p) + p/s). s=inf (a removed stage) is allowed."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be a fraction between 0 and 1")
    if s <= 0:
        raise ValueError("s must be positive (use float('inf') to remove a stage)")
    serial = (1.0 - p) + (0.0 if s == float("inf") else p / s)
    if serial <= 0:
        return float("inf")
    return 1.0 / serial


def amdahl_new_turn(base_turn_s: float, p: float, s: float) -> float:
    """New turn time after speeding a fraction p of the turn by factor s."""
    if base_turn_s <= 0:
        raise ValueError("base_turn_s must be positive")
    return base_turn_s / amdahl_speedup(p, s)


# --- §5 Tails -------------------------------------------------------------

def tail_probability(per_stage_slow: float, stages: int) -> float:
    """P(at least one of `stages` independent stages is slow) = 1 - (1-q)^n (02 §5)."""
    if not 0.0 <= per_stage_slow <= 1.0:
        raise ValueError("per_stage_slow must be a probability")
    if stages < 0:
        raise ValueError("stages must be non-negative")
    return 1.0 - (1.0 - per_stage_slow) ** stages


# --- §6 Energy and cost ---------------------------------------------------

def energy_joules(gpu_watts: float, gpu_seconds: float,
                  cpu_watts: float = 0.0, cpu_seconds: float = 0.0) -> float:
    """E_turn ≈ P_gpu*t_gpu + P_cpu*t_cpu (02 §6), in joules."""
    for value in (gpu_watts, gpu_seconds, cpu_watts, cpu_seconds):
        if value < 0:
            raise ValueError("power and time must be non-negative")
    return gpu_watts * gpu_seconds + cpu_watts * cpu_seconds


def cost_per_turn(energy_j: float, price_per_kwh: float,
                  hardware_cost: float = 0.0, turns_over_lifetime: float = 0.0) -> float:
    """C_turn = E*price + C_hardware/N_turns (02 §6). Amortisation is 0 when N=0."""
    if energy_j < 0 or price_per_kwh < 0:
        raise ValueError("energy and price must be non-negative")
    kwh = energy_j / 3.6e6
    amortisation = hardware_cost / turns_over_lifetime if turns_over_lifetime else 0.0
    return kwh * price_per_kwh + amortisation


# --- Splitting real traffic into cost-model terms -------------------------

@dataclass(frozen=True)
class CallRates:
    """Prefill/decode rates derived from one Ollama call's token counts (02 §2).

    Fields mirror the numeric allowlist recorded by ``operations.record_attempt``.
    Durations from Ollama are nanoseconds; rates are tokens/second.
    """

    prompt_tokens: int | None = None
    output_tokens: int | None = None
    prefill_tok_s: float | None = None
    decode_tok_s: float | None = None
    load_seconds: float | None = None
    total_seconds: float | None = None
    cold: bool | None = None


def split_call_rates(fields: dict | None) -> CallRates:
    """Split one call's measurement into prefill/decode rates without any content.

    `fields` is the numeric allowlist from a provider response (Ollama's
    `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, `eval_duration`,
    `load_duration`, `total_duration`; durations in nanoseconds). Missing or
    non-positive values leave the derived rate as None rather than guessing.
    """
    fields = fields or {}

    def _num(key):
        value = fields.get(key)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None

    prompt_tokens = _num("prompt_eval_count")
    prompt_ns = _num("prompt_eval_duration")
    output_tokens = _num("eval_count")
    output_ns = _num("eval_duration")
    load_ns = _num("load_duration")
    total_ns = _num("total_duration")

    def _rate(tokens, duration_ns):
        if tokens and duration_ns and duration_ns > 0:
            return round(tokens / (duration_ns / 1e9), 3)
        return None

    load_seconds = round(load_ns / 1e9, 3) if load_ns is not None else None
    return CallRates(
        prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        prefill_tok_s=_rate(prompt_tokens, prompt_ns),
        decode_tok_s=_rate(output_tokens, output_ns),
        load_seconds=load_seconds,
        total_seconds=round(total_ns / 1e9, 3) if total_ns is not None else None,
        cold=(load_seconds is not None and load_seconds > 0.5) if load_seconds is not None else None,
    )


def call_record(stage: str, fields: dict | None) -> dict:
    """A JSON-safe per-call metrics row for `rag_metrics['calls']` (02 §8).

    Contains only the stage name and numeric measurements — never the prompt,
    the question, or any provider response body.
    """
    rates = split_call_rates(fields)
    row = {"stage": stage}
    for key in ("prompt_tokens", "output_tokens", "prefill_tok_s", "decode_tok_s",
                "load_seconds", "total_seconds", "cold"):
        value = getattr(rates, key)
        if value is not None:
            row[key] = value
    return row
