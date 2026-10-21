"""Prepare the local tokenizer without changing the shared Python/model stack."""
import hashlib
from pathlib import Path

import httpx
from tokenizers import Tokenizer

from assistant.config import settings

TOKENIZERS = {
    "llama3.1": ("NousResearch/Meta-Llama-3.1-8B-Instruct", "d10aef7999a2b5ba950ab3974312feeedbfe0b77"),
    "qwen3": ("Qwen/Qwen3-8B", "b968826d9c46dd6066d109eabc6255188de91218"),
    "qwen3.5": ("Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"),
}


def main():
    target = Path(settings.OLLAMA_TOKENIZER_PATH).expanduser()
    family = settings.OLLAMA_MODEL.split(":")[0]
    if family not in TOKENIZERS:
        raise SystemExit("For another model, set OLLAMA_TOKENIZER_PATH to its matching tokenizer.json.")
    if not target.is_file():
        repo, revision = TOKENIZERS[family]
        response = httpx.get(f"https://huggingface.co/{repo}/resolve/{revision}/tokenizer.json",
                             follow_redirects=True, timeout=120)
        response.raise_for_status()
        Tokenizer.from_str(response.text)  # Validate before publishing the cache file.
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(response.content)
        temporary.replace(target)
    Tokenizer.from_file(str(target))
    print(f"Tokenizer ready: {target}")
    print(f"SHA256: {hashlib.sha256(target.read_bytes()).hexdigest()}")
    try:
        response = httpx.get(settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags", timeout=5, trust_env=False)
        response.raise_for_status()
        names = {model["name"] for model in response.json()["models"]}
    except (httpx.HTTPError, ValueError, KeyError):
        raise SystemExit("Tokenizer is ready. Start Ollama with ollama serve, then rerun this check.")
    if settings.OLLAMA_MODEL not in names:
        raise SystemExit(f"Run: ollama pull {settings.OLLAMA_MODEL}")
    print(f"Ollama model ready: {settings.OLLAMA_MODEL}")


if __name__ == "__main__":
    main()
