"""Sentence-aware chunking with overlap. Chunks never cross section boundaries."""

import re
from dataclasses import dataclass

from app.rag.documents import SourceDocument

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])|\n+")


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source_id: str
    title: str
    section: str
    url: str
    publisher: str
    license: str
    attribution: str
    section_index: int
    chunk_index: int

    @property
    def embedding_text(self) -> str:
        """Text sent to the embedding model: title and section give the passage context."""
        return f"{self.title}. {self.section}\n{self.text}"

    def metadata(self) -> dict[str, str | int]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "section": self.section,
            "url": self.url,
            "publisher": self.publisher,
            "license": self.license,
            "attribution": self.attribution,
            "section_index": self.section_index,
            "chunk_index": self.chunk_index,
        }


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.split(text) if part and part.strip()]


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_document(document: SourceDocument, *, max_words: int, overlap_words: int) -> list[Chunk]:
    if overlap_words >= max_words:
        raise ValueError("overlap_words must be smaller than max_words")

    chunks: list[Chunk] = []
    for section_index, section in enumerate(document.sections):
        for chunk_index, text in enumerate(_pack(split_sentences(section.text), max_words, overlap_words)):
            chunks.append(
                Chunk(
                    id=f"{document.id}:{section_index}:{chunk_index}",
                    text=text,
                    source_id=document.id,
                    title=document.title,
                    section=section.heading,
                    url=document.url,
                    publisher=document.publisher,
                    license=document.license,
                    attribution=document.attribution,
                    section_index=section_index,
                    chunk_index=chunk_index,
                )
            )
    return chunks


def _pack(sentences: list[str], max_words: int, overlap_words: int) -> list[str]:
    """Greedily pack sentences into chunks; each new chunk repeats trailing sentences for overlap."""
    chunks: list[list[str]] = []
    current: list[str] = []
    for sentence in sentences:
        if current and _word_count(" ".join(current + [sentence])) > max_words:
            chunks.append(current)
            overlap: list[str] = []
            for previous in reversed(current):
                if _word_count(" ".join([previous] + overlap)) > overlap_words:
                    break
                overlap.insert(0, previous)
            current = overlap
        current.append(sentence)
    if current and (not chunks or current != chunks[-1][-len(current):]):
        chunks.append(current)
    return ["\n".join(chunk) for chunk in chunks]
