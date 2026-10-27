from pydantic import BaseModel, Field, field_validator

MAX_TESTS_PER_REQUEST = 50


class EvidenceRequest(BaseModel):
    test_names: list[str] = Field(min_length=1, max_length=MAX_TESTS_PER_REQUEST)

    @field_validator("test_names")
    @classmethod
    def _clean(cls, names: list[str]) -> list[str]:
        cleaned: list[str] = []
        for name in names:
            name = " ".join(name.split())
            if not name or len(name) > 100:
                raise ValueError("Each test name must be 1-100 characters.")
            if name.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(name)
        return cleaned


class EvidencePassage(BaseModel):
    """A retrieved passage of general reference information. Not evidence about the patient."""

    citation_id: str = Field(description="Stable within one response, e.g. 'E1'.")
    chunk_id: str
    source_id: str
    title: str
    section: str
    url: str
    publisher: str
    attribution: str
    text: str
    similarity: float


class TestEvidence(BaseModel):
    __test__ = False  # not a pytest test class

    test_name: str
    query: str
    citation_ids: list[str]


class EvidenceResponse(BaseModel):
    passages: list[EvidencePassage]
    tests: list[TestEvidence]
    unmatched_tests: list[str] = Field(
        description="Tests with no passage above the relevance threshold. No background is given for these."
    )
    embedding_model: str
    min_similarity: float


class KnowledgeBaseStatus(BaseModel):
    index_ready: bool
    chunk_count: int = 0
    source_count: int = 0
    embedding_model: str
    built_at: str | None = None
