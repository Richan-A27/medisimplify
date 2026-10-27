"""End-to-end summarization: report facts -> (evidence) -> prompt -> LLM -> parse -> validate.

Each stage is explicit and its outputs are returned, so results can be audited without exposing any
model reasoning.
"""

import json
import logging
import time
from collections.abc import Callable

from pydantic import ValidationError

from app.prompts.builder import build_prompt
from app.rag.retrieval import Retriever
from app.schemas.evidence import EvidencePassage, TestEvidence
from app.schemas.report import ExtractionResponse
from app.schemas.summary import Strategy, SummaryOutput, SummaryResponse
from app.safety.validation import validate_summary
from app.services.llm import LLMClient, LLMInvalidOutputError

logger = logging.getLogger("medisimplify.summarizer")

DISCLAIMER = (
    "MediSimplify is an educational prototype. This summary was generated automatically and may contain "
    "errors. It is not a diagnosis or medical advice. Discuss your results with a qualified healthcare "
    "professional."
)


class NoMeasurementsError(Exception):
    code = "no_measurements"
    status_code = 422
    message = "No test results were recognised in this report, so there is nothing to summarise."


def parse_output(text: str) -> SummaryOutput:
    try:
        return SummaryOutput.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise LLMInvalidOutputError() from exc


def summarize(
    extraction: ExtractionResponse,
    strategy: Strategy,
    llm: LLMClient,
    get_retriever: Callable[[], Retriever],
) -> SummaryResponse:
    if not extraction.measurements:
        raise NoMeasurementsError()

    evidence: list[EvidencePassage] = []
    test_evidence: list[TestEvidence] = []
    unmatched: list[str] = []
    if strategy == "rag":
        names = list(dict.fromkeys(m.test_name for m in extraction.measurements))
        retrieved = get_retriever().retrieve_for_tests(names)
        evidence, test_evidence, unmatched = retrieved.passages, retrieved.tests, retrieved.unmatched_tests

    prompt = build_prompt(
        strategy,
        extraction.measurements,
        extraction.warnings,
        evidence=evidence if strategy == "rag" else None,
        unmatched_tests=unmatched,
    )
    started = time.perf_counter()
    result = llm.generate(prompt)
    output = parse_output(result.text)
    validation = validate_summary(output, extraction.measurements, strategy, evidence, test_evidence)

    logger.info(
        "Summary: strategy=%s model=%s prompt=%s status=%s issues=%d tokens=%s/%s latency_ms=%d",
        strategy,
        result.model,
        prompt.sha256[:12],
        validation.status,
        len(validation.issues),
        result.usage.prompt_tokens,
        result.usage.output_tokens,
        result.latency_ms,
    )
    return SummaryResponse(
        strategy=strategy,
        model=result.model,
        prompt_version=prompt.version,
        prompt_sha256=prompt.sha256,
        output=output,
        validation=validation,
        measurements=extraction.measurements,
        document_warnings=extraction.warnings,
        evidence=evidence,
        unmatched_tests=unmatched,
        usage=result.usage,
        latency_ms=result.latency_ms or int((time.perf_counter() - started) * 1000),
        disclaimer=DISCLAIMER,
    )
