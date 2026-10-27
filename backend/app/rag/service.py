"""Process-wide access to the knowledge base, created lazily so startup stays fast."""

import threading

from app.config import Settings
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.retrieval import KnowledgeBaseUnavailableError, Retriever
from app.rag.store import VectorStore
from app.schemas.evidence import KnowledgeBaseStatus


class KnowledgeBase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._retriever: Retriever | None = None
        self._lock = threading.Lock()

    def _store(self) -> VectorStore | None:
        # Avoid creating an empty index directory just by checking status.
        if not self.settings.index_dir.exists():
            return None
        return VectorStore(self.settings.index_dir)

    def status(self) -> KnowledgeBaseStatus:
        store = self._store()
        info = store.info() if store else None
        if not info:
            return KnowledgeBaseStatus(index_ready=False, embedding_model=self.settings.embedding_model)
        return KnowledgeBaseStatus(
            index_ready=info.get("chunk_count", 0) > 0
            and info.get("embedding_model") == self.settings.embedding_model,
            chunk_count=info.get("chunk_count", 0),
            source_count=info.get("source_count", 0),
            embedding_model=str(info.get("embedding_model", self.settings.embedding_model)),
            built_at=info.get("built_at"),
        )

    def retriever(self) -> Retriever:
        with self._lock:
            if self._retriever is None:
                if not self.settings.index_dir.exists():
                    raise KnowledgeBaseUnavailableError()
                self._retriever = Retriever(
                    VectorStore(self.settings.index_dir),
                    SentenceTransformerEmbedder(self.settings.embedding_model),
                    top_k=self.settings.rag_top_k,
                    min_similarity=self.settings.rag_min_similarity,
                )
            return self._retriever
