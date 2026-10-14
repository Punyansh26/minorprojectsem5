"""Unified LLM client with local Ollama + OpenAI/Groq backend support and SQLite caching."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

from .config import Config
from .store import KVCache
from .textnorm import sha256

log = logging.getLogger(__name__)


class LLMClient:
    """Caching LLM client supporting local Ollama and OpenAI-compatible APIs (Groq/vLLM)."""

    def __init__(self, cfg: Config, cache: KVCache | None = None):
        self.cfg = cfg.llm
        self.cache = cache
        self._client = httpx.Client(timeout=self.cfg.timeout_s)

    def generate(self, prompt: str, system: str = "", json_mode: bool = False) -> str:
        """Call LLM with content-addressed caching."""
        cache_key = sha256(f"{self.cfg.backend}:{self.cfg.model}:{system}:{prompt}:{json_mode}")
        if self.cache:
            hit = self.cache.get("llm", cache_key)
            if hit is not None:
                return hit

        # Dispatch backend
        if self.cfg.backend == "ollama":
            result = self._call_ollama(prompt, system, json_mode)
        else:
            result = self._call_openai(prompt, system, json_mode)

        if self.cache and result:
            self.cache.put("llm", cache_key, result)

        return result

    def _call_ollama(self, prompt: str, system: str, json_mode: bool) -> str:
        url = f"{self.cfg.base_url.rstrip('/')}/api/generate"
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": self.cfg.temperature,
                "num_ctx": self.cfg.num_ctx,
                "num_predict": 1024,
            },
        }
        if json_mode:
            payload["format"] = "json"

        for attempt in range(self.cfg.max_retries):
            try:
                resp = self._client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "").strip()
            except Exception as exc:
                log.warning("Ollama call failed (attempt %d): %s", attempt + 1, exc)
                time.sleep(1.5 ** attempt)

        raise RuntimeError(f"Ollama generation failed after {self.cfg.max_retries} retries")

    def _call_openai(self, prompt: str, system: str, json_mode: bool) -> str:
        api_key = os.environ.get(self.cfg.api_key_env, "")
        url = f"{self.cfg.openai_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.cfg.openai_model,
            "messages": messages,
            "temperature": self.cfg.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        for attempt in range(self.cfg.max_retries):
            try:
                resp = self._client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                log.warning("OpenAI/Groq call failed (attempt %d): %s", attempt + 1, exc)
                time.sleep(1.5 ** attempt)

        raise RuntimeError(f"OpenAI/Groq generation failed after {self.cfg.max_retries} retries")
