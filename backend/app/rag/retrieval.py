"""Retrieve general reference passages for the tests found in a report.

Queries contain only test names (never patient values or identifiers). Passages below the similarity
threshold are dropped, so a test with no relevant reference gets no background rather than a weak match.
"""

import re

from app.rag.embeddings import Embedder
from app.rag.store import VectorStore
from app.schemas.evidence import EvidencePassage, EvidenceResponse, TestEvidence

# Expands common lab abbreviations so short names embed meaningfully. This only rewrites the search
# query; it adds no medical content to the response.
ABBREVIATIONS: dict[str, str] = {
    "wbc": "white blood cell count",
    "rbc": "red blood cell count",
    "hb": "hemoglobin",
    "hgb": "hemoglobin",
    "hct": "hematocrit",
    "plt": "platelet count",
    "hba1c": "hemoglobin A1C",
    "a1c": "hemoglobin A1C",
    "ldl": "LDL cholesterol",
    "hdl": "HDL cholesterol",
    "tsh": "thyroid-stimulating hormone",
    "crp": "C-reactive protein",
    "bun": "blood urea nitrogen",
    "egfr": "estimated glomerular filtration rate",
    "alt": "alanine aminotransferase liver enzyme",
    "ast": "aspartate aminotransferase liver enzyme",
    "na": "sodium",
    "k": "potassium",
    "cbc": "complete blood count",
    "bmp": "basic metabolic panel",
    "cmp": "comprehensive metabolic panel",
}


class KnowledgeBaseUnavailableError(RuntimeError):
    code = "knowledge_base_unavailable"
    message = (
        "The reference knowledge base has not been built. "
        "Run `.venv/bin/python -m scripts.ingest_knowledge_base` in backend/ and restart the server."
    )


def build_query(test_name: str) -> str:
    words = [ABBREVIATIONS.get(word.lower(), word) for word in re.split(r"[\s,]+", test_name) if word]
    return f"{' '.join(words)} test: what it measures and what results mean"


class Retriever:
    def __init__(self, store: VectorStore, embedder: Embedder, *, top_k: int, min_similarity: float) -> None:
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.min_similarity = min_similarity

    def retrieve_for_tests(self, test_names: list[str]) -> EvidenceResponse:
        info = self.store.info()
        if not info or not info.get("chunk_count"):
            raise KnowledgeBaseUnavailableError()
        if info.get("embedding_model") != self.embedder.model_name:
            raise KnowledgeBaseUnavailableError(
                "The index was built with a different embedding model. Rebuild it with the ingestion command."
            )

        passages: dict[str, EvidencePassage] = {}
        tests: list[TestEvidence] = []
        unmatched: list[str] = []
        for name in test_names:
            query = build_query(name)
            hits = [
                hit
                for hit in self.store.query(self.embedder.embed_query(query), self.top_k)
                if hit.similarity >= self.min_similarity
            ]
            citation_ids: list[str] = []
            for hit in hits:
                passage = passages.get(hit.chunk_id)
                if passage is None:
                    meta = hit.metadata
                    passage = EvidencePassage(
                        citation_id=f"E{len(passages) + 1}",
                        chunk_id=hit.chunk_id,
                        source_id=str(meta["source_id"]),
                        title=str(meta["title"]),
                        section=str(meta["section"]),
                        url=str(meta["url"]),
                        publisher=str(meta["publisher"]),
                        attribution=str(meta["attribution"]),
                        text=hit.text,
                        similarity=round(hit.similarity, 4),
                    )
                    passages[hit.chunk_id] = passage
                elif hit.similarity > passage.similarity:
                    passage.similarity = round(hit.similarity, 4)
                citation_ids.append(passage.citation_id)
            if not citation_ids:
                unmatched.append(name)
            tests.append(TestEvidence(test_name=name, query=query, citation_ids=citation_ids))

        return EvidenceResponse(
            passages=list(passages.values()),
            tests=tests,
            unmatched_tests=unmatched,
            embedding_model=self.embedder.model_name,
            min_similarity=self.min_similarity,
        )
