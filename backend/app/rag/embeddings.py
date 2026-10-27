"""Local text embeddings via Sentence Transformers (no API key or paid service)."""

import threading
from typing import Protocol


class Embedder(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    """Loads the model on first use; the first call downloads it from Hugging Face if not cached."""

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):  # type: ignore[no-untyped-def]
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # heavy import, deferred

                self._model = SentenceTransformer(self.model_name, device="cpu")
            return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
