"""ChromaDB persistence for reference chunks. Embeddings are supplied by our own Embedder."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.rag.chunking import Chunk

COLLECTION_NAME = "medical_references"


@dataclass(frozen=True)
class StoredHit:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    similarity: float  # cosine similarity in [-1, 1]; higher is more similar


class VectorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )

    def _collection(self):  # type: ignore[no-untyped-def]
        return self._client.get_collection(COLLECTION_NAME)

    def exists(self) -> bool:
        return any(c.name == COLLECTION_NAME for c in self._client.list_collections())

    def info(self) -> dict[str, Any] | None:
        if not self.exists():
            return None
        collection = self._collection()
        return {"chunk_count": collection.count(), **(collection.metadata or {})}

    def rebuild(self, chunks: list[Chunk], embeddings: list[list[float]], metadata: dict[str, Any]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if self.exists():
            self._client.delete_collection(COLLECTION_NAME)
        collection = self._client.create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine", **metadata}
        )
        batch = 500
        for start in range(0, len(chunks), batch):
            part = chunks[start : start + batch]
            collection.add(
                ids=[c.id for c in part],
                documents=[c.text for c in part],
                metadatas=[c.metadata() for c in part],
                embeddings=embeddings[start : start + batch],
            )

    def query(self, embedding: list[float], top_k: int) -> list[StoredHit]:
        result = self._collection().query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return [
            StoredHit(chunk_id=chunk_id, text=text, metadata=dict(meta), similarity=1.0 - distance)
            for chunk_id, text, meta, distance in zip(
                result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
        ]
