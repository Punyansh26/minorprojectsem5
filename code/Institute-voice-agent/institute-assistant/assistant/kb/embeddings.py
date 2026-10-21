"""Use identical local E5 preprocessing for corpus, queries, and cached vectors."""
from pathlib import Path

from langchain_core.embeddings import Embeddings

from assistant.config import settings
from assistant.kb.common import digest, read_json, write_json


class LocalE5(Embeddings):
    """Keep prefixing explicit; query clustering must not use the passage prefix."""

    def __init__(self, model_path: str, cache_dir: str | None = None, revision: str = ""):
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(settings.KB_THREADS)
        self.model = SentenceTransformer(model_path, device="cpu", local_files_only=True)
        self.model.max_seq_length = 512
        self.tokenizer = self.model.tokenizer
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.profile = f"{settings.KB_EMBEDDING_MODEL}:{revision}:normalized:passage-query:v1"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Reuse unchanged vectors and bound memory through model-side batches."""
        vectors = [None] * len(texts)
        missing = []
        for i, text in enumerate(texts):
            key = digest(self.profile + "\n" + text)
            path = self.cache_dir / f"{key}.json" if self.cache_dir else None
            cached = read_json(path) if path else None
            if cached is not None:
                vectors[i] = cached
            else:
                missing.append((i, path))
        for start in range(0, len(missing), settings.KB_BATCH_SIZE):
            batch = missing[start:start + settings.KB_BATCH_SIZE]
            output = self.model.encode(["passage: " + texts[i] for i, _ in batch],
                                       normalize_embeddings=True, batch_size=settings.KB_BATCH_SIZE,
                                       show_progress_bar=False).tolist()
            for (i, path), vector in zip(batch, output):
                vectors[i] = vector
                if path:
                    write_json(path, vector)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Embed the retrieval question using the training-time query prefix."""
        return self.model.encode("query: " + text, normalize_embeddings=True).tolist()

    def embed_questions(self, texts: list[str]) -> list[list[float]]:
        """Use symmetric question embeddings for offline gap clustering."""
        return self.model.encode(["query: " + t for t in texts], normalize_embeddings=True,
                                 batch_size=settings.KB_BATCH_SIZE).tolist()
