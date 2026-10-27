"""Build (or rebuild) the ChromaDB index from knowledge_base/sources.

Usage (from backend/):  .venv/bin/python -m scripts.ingest_knowledge_base

The first run downloads the embedding model (about 90 MB) from Hugging Face; later runs use the cache.
Restart the backend afterwards so it picks up the new index.
"""

import sys
import time

from app.config import get_settings
from app.rag.documents import DocumentError
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.ingest import ingest
from app.rag.store import VectorStore


def main() -> int:
    settings = get_settings()
    started = time.perf_counter()
    try:
        report = ingest(
            settings.knowledge_base_dir / "sources",
            VectorStore(settings.index_dir),
            SentenceTransformerEmbedder(settings.embedding_model),
            max_words=settings.chunk_max_words,
            overlap_words=settings.chunk_overlap_words,
        )
    except DocumentError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Indexed {report.chunk_count} chunks from {report.source_count} sources "
        f"with {report.embedding_model} in {time.perf_counter() - started:.1f}s"
    )
    print(f"Index: {settings.index_dir}")
    print(f"Corpus SHA-256: {report.corpus_sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
