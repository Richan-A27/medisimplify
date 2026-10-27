"""Deterministic test doubles so RAG unit tests run without downloading a model."""

import hashlib
import json
import math
import re
from pathlib import Path

from app.rag.documents import Section, SourceDocument, render_document

DIMENSIONS = 256
# Words from the retrieval query template; ignoring them keeps fake similarities topic-driven.
STOPWORDS = {"test", "what", "measures", "results", "mean", "and", "the"}


class HashingEmbedder:
    """Bag-of-words hashing embedder: texts sharing words get similar vectors."""

    model_name = "test/hashing-embedder"

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            if len(word) < 3 or word in STOPWORDS:
                continue
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def make_document(doc_id: str, title: str, sections: dict[str, str]) -> SourceDocument:
    return SourceDocument(
        id=doc_id,
        title=title,
        publisher="Test Publisher",
        url=f"https://example.test/{doc_id}",
        license="Test licence",
        attribution="Source: Test Publisher",
        sections=[Section(heading, text) for heading, text in sections.items()],
    )


SAMPLE_DOCUMENTS = [
    make_document(
        "doc-hemoglobin",
        "Hemoglobin Test",
        {
            "What is a hemoglobin test?": "A hemoglobin test measures hemoglobin in red blood cells. "
            "Hemoglobin carries oxygen through the body.",
            "What do the results mean?": "Hemoglobin results are compared with a reference range.",
        },
    ),
    make_document(
        "doc-glucose",
        "Blood Glucose Test",
        {"What is a blood glucose test?": "A blood glucose test measures glucose sugar levels in blood."},
    ),
    make_document(
        "doc-potassium",
        "Potassium Blood Test",
        {"What is a potassium test?": "A potassium blood test measures potassium electrolyte levels."},
    ),
]


def write_corpus(sources_dir: Path, documents: list[SourceDocument]) -> None:
    (sources_dir / "documents").mkdir(parents=True, exist_ok=True)
    manifest = {"sources": [{"id": d.id, "url": d.url} for d in documents]}
    (sources_dir / "manifest.json").write_text(json.dumps(manifest))
    for document in documents:
        (sources_dir / "documents" / f"{document.id}.md").write_text(render_document(document))
