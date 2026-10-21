"""Read-only run collector for the chapter 12 §2.6 system-resource metrics (§11 item 1).

Wraps a run with sampling that is *purely observational*: it reads ollama `/api/ps` residency,
`nvidia-smi --query-gpu=power.draw` [R1223] and Intel RAPL `/sys/class/powercap/intel-rapl*`
[R1224] alongside the `rag_metrics.stage_ms` the agent already emits. Every probe degrades
gracefully when the source is absent (no GPU, no RAPL, ollama down) so the module imports and
runs on any machine, including CI.

Nothing here mutates state, loads a model, or writes into Demo2's own `data/` directories.
The two things it enforces for the gate layer:

  * `residency_stable(before, after)` — the §7.1 pin: size_vram / context_length / digest must
    be unchanged across the run, else the run is not comparable.
  * `EnergySampler` — integrates power over a turn window (∫P dt) to produce Wh/turn, the
    [Measured-here] replacement for the [Estimated] "$0.60/month" in [01 §6].

Design: the standard library only (`urllib`, `subprocess`, `glob`, `time`, `json`). NumPy is
not required. `urllib`/`subprocess` are used with fixed, non-interpolated arguments.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


def _ollama_base_url() -> str:
    """Prefer Demo2's configured URL; fall back to the documented default. No settings import."""
    return (os.environ.get("OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://127.0.0.1:11434").rstrip("/")


# --------------------------------------------------------------------------- residency (§7.1)


def read_residency(*, timeout: float = 1.0) -> dict:
    """Snapshot ollama `/api/ps`: the first loaded model's size_vram / context / digest.

    Returns ``{"available": bool, ...}``. Never raises on a missing/empty server; the caller
    decides what an unavailable snapshot means for the gate.
    """
    url = _ollama_base_url() + "/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:   # nosec: fixed localhost URL
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001 — any transport/parse failure means "unavailable"
        return {"available": False, "error": type(error).__name__}
    models = payload.get("models") or []
    if not models:
        return {"available": True, "loaded": 0}
    top = models[0]
    return {
        "available": True,
        "loaded": len(models),
        "name": top.get("name") or top.get("model"),
        "size": top.get("size"),
        "size_vram": top.get("size_vram"),
        "total": top.get("size"),
        "context_length": (top.get("context_length")
                           or (top.get("details") or {}).get("context_length")),
        "digest": top.get("digest"),
    }


def residency_stable(before: dict, after: dict) -> bool:
    """§7.1 pin: True only if size_vram, context_length and digest match across the run.

    An unavailable snapshot on either side is treated as *unstable* (conservative): a gate
    must not silently pass when residency could not be confirmed.
    """
    if not before.get("available") or not after.get("available"):
        return False
    if before.get("loaded", 0) == 0 or after.get("loaded", 0) == 0:
        return False
    return all(before.get(key) == after.get(key)
               for key in ("size_vram", "context_length", "digest"))


# --------------------------------------------------------------------------- GPU power / VRAM


def _nvidia_smi_query(field_name: str) -> Optional[float]:
    """Single `nvidia-smi --query-gpu=<field>` reading in float; None if no GPU/tool."""
    try:
        out = subprocess.run(   # nosec: fixed argument vector, no shell
            ["nvidia-smi", f"--query-gpu={field_name}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2.0, check=True,
        ).stdout.strip().splitlines()
    except Exception:  # noqa: BLE001 — FileNotFoundError, CalledProcessError, timeout …
        return None
    if not out:
        return None
    try:
        return float(out[0].split(",")[0].strip())
    except ValueError:
        return None


def read_gpu_power_watts() -> Optional[float]:
    """Instantaneous GPU power draw in watts (nvidia-smi power.draw) [R1223]."""
    return _nvidia_smi_query("power.draw")


def read_gpu_vram_used_mib() -> Optional[float]:
    """GPU memory used in MiB (nvidia-smi memory.used) — the G-vram peak source."""
    return _nvidia_smi_query("memory.used")


# --------------------------------------------------------------------------- CPU RAPL energy


def _rapl_domains() -> list[str]:
    """RAPL package energy_uj files under powercap, if the kernel exposes them [R1224]."""
    return sorted(glob.glob("/sys/class/powercap/intel-rapl:*/energy_uj"))


def read_rapl_energy_uj() -> Optional[int]:
    """Summed RAPL package energy counter in microjoules; None if RAPL is unavailable.

    Counters wrap; use two reads and `max_energy_range_uj` to handle wrap in `EnergySampler`.
    """
    domains = _rapl_domains()
    if not domains:
        return None
    total = 0
    read_any = False
    for path in domains:
        try:
            with open(path) as handle:
                total += int(handle.read().strip())
                read_any = True
        except (OSError, ValueError):
            continue
    return total if read_any else None


# --------------------------------------------------------------------------- energy integrator


@dataclass
class EnergySampler:
    """Integrate GPU power (∫P dt) and read RAPL deltas over a turn window → Wh/turn (§2.6).

    Usage::

        s = EnergySampler(); s.start()
        ...  # run one turn
        reading = s.stop()     # {"gpu_wh": ..., "cpu_wh": ..., "seconds": ...}

    GPU energy is a trapezoidal integral of sampled `power.draw`; CPU energy is the RAPL
    counter delta. Both are ``None`` when the source is absent, never fabricated.
    """
    gpu_samples: list[tuple[float, float]] = field(default_factory=list)  # (t, watts)
    _rapl_start: Optional[int] = None
    _t_start: Optional[float] = None
    _clock: callable = time.monotonic

    def start(self) -> None:
        self.gpu_samples = []
        self._t_start = self._clock()
        self._rapl_start = read_rapl_energy_uj()
        self.sample()

    def sample(self) -> None:
        """Take one GPU power sample; call periodically during the turn."""
        watts = read_gpu_power_watts()
        if watts is not None:
            self.gpu_samples.append((self._clock(), watts))

    def stop(self) -> dict:
        """Close the window and return integrated energy for the turn."""
        self.sample()
        t_end = self._clock()
        seconds = (t_end - self._t_start) if self._t_start is not None else 0.0
        gpu_wh = self._integrate_gpu_wh()
        cpu_wh = None
        rapl_end = read_rapl_energy_uj()
        if self._rapl_start is not None and rapl_end is not None:
            delta_uj = rapl_end - self._rapl_start
            if delta_uj < 0:  # counter wrapped; best-effort single-wrap correction
                delta_uj += sum(self._rapl_max_ranges())
            cpu_wh = delta_uj / 1e6 / 3600.0
        return {"seconds": seconds, "gpu_wh": gpu_wh, "cpu_wh": cpu_wh,
                "gpu_samples": len(self.gpu_samples),
                "total_wh": None if gpu_wh is None and cpu_wh is None
                            else (gpu_wh or 0.0) + (cpu_wh or 0.0)}

    def _integrate_gpu_wh(self) -> Optional[float]:
        if len(self.gpu_samples) < 2:
            return None
        joules = 0.0
        for (t0, w0), (t1, w1) in zip(self.gpu_samples, self.gpu_samples[1:]):
            joules += (w0 + w1) / 2.0 * (t1 - t0)   # trapezoid
        return joules / 3600.0

    @staticmethod
    def _rapl_max_ranges() -> list[int]:
        ranges = []
        for energy_path in _rapl_domains():
            max_path = energy_path.replace("energy_uj", "max_energy_range_uj")
            try:
                with open(max_path) as handle:
                    ranges.append(int(handle.read().strip()))
            except (OSError, ValueError):
                continue
        return ranges


# --------------------------------------------------------------------------- stage_ms passthrough


def collect_stage_ms(rag_metrics: dict | None) -> dict:
    """Pass through `rag_metrics.stage_ms` + the cache/model-call fields the agent emits.

    Read-only: it reshapes what `agent_bridge.ask` already returns so a collector run records
    per-stage attribution without touching the agent. Missing keys become ``None``.
    """
    rag_metrics = rag_metrics or {}
    stage_ms = rag_metrics.get("stage_ms") or {}
    return {
        "stage_ms": dict(stage_ms),
        "model_calls": rag_metrics.get("model_calls"),
        "router_path": rag_metrics.get("router_path"),
        "retrieval_cache": rag_metrics.get("retrieval_cache"),
        "draft_cache": rag_metrics.get("draft_cache"),
        "provider": rag_metrics.get("provider"),
        "model": rag_metrics.get("model"),
    }


def snapshot_environment() -> dict:
    """One-shot environment record for a run manifest (residency + VRAM + power availability)."""
    return {
        "residency": read_residency(),
        "gpu_vram_used_mib": read_gpu_vram_used_mib(),
        "gpu_power_watts": read_gpu_power_watts(),
        "rapl_available": bool(_rapl_domains()),
        "ollama_base_url": _ollama_base_url(),
        "captured_at": time.time(),
    }


if __name__ == "__main__":  # pragma: no cover — manual probe, read-only
    print(json.dumps(snapshot_environment(), indent=2))
