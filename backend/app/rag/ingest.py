"""Rebuild the vector index from the approved reference documents."""

import datetime as dt
import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.rag.chunking import chunk_document
from app.rag.documents import load_documents
from app.rag.embeddings import Embedder
from app.rag.store import VectorStore


@dataclass(frozen=True)
class IngestionReport:
    source_count: int
    chunk_count: int
    embedding_model: str
    corpus_sha256: str


def ingest(
    sources_dir: Path,
    store: VectorStore,
    embedder: Embedder,
    *,
    max_words: int,
    overlap_words: int,
) -> IngestionReport:
    documents = load_documents(sources_dir)
    chunks = [
        chunk
        for document in documents
        for chunk in chunk_document(document, max_words=max_words, overlap_words=overlap_words)
    ]
    if not chunks:
        raise ValueError("No chunks were produced from the reference documents.")

    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.id.encode())
        digest.update(chunk.text.encode())
    corpus_sha256 = digest.hexdigest()

    embeddings = embedder.embed_documents([chunk.embedding_text for chunk in chunks])
    store.rebuild(
        chunks,
        embeddings,
        metadata={
            "embedding_model": embedder.model_name,
            "source_count": len(documents),
            "chunk_max_words": max_words,
            "chunk_overlap_words": overlap_words,
            "corpus_sha256": corpus_sha256,
            "built_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        },
    )
    return IngestionReport(len(documents), len(chunks), embedder.model_name, corpus_sha256)
