"""Orchestrates validation, text extraction, measurement parsing and document warnings."""

import logging
import time

from app.safety.injection import find_instruction_like_pages
from app.schemas.report import DocumentWarning, ExtractionResponse, PageTextOut
from app.services.pdf_extraction import TextExtractor, validate_pdf_bytes
from app.services.report_parser import parse_measurements

logger = logging.getLogger("medisimplify.extraction")


def extract_report(data: bytes, *, extractor: TextExtractor, max_bytes: int) -> ExtractionResponse:
    started = time.perf_counter()
    validate_pdf_bytes(data, max_bytes=max_bytes)
    document = extractor.extract(data)
    measurements = parse_measurements(document.pages)

    warnings: list[DocumentWarning] = []
    for page_number in document.pages_without_text:
        warnings.append(
            DocumentWarning(
                code="page_without_text",
                message="This page has no readable text (it may be a scanned image) and was skipped.",
                page_number=page_number,
            )
        )
    for page_number in find_instruction_like_pages(document.pages):
        warnings.append(
            DocumentWarning(
                code="possible_embedded_instructions",
                message="This page contains text that resembles instructions to an AI system. "
                "It is treated as report content only and will not be followed.",
                page_number=page_number,
            )
        )
    if not measurements:
        warnings.append(
            DocumentWarning(
                code="no_measurements_found",
                message="No test results were recognised automatically. Review the extracted text; "
                "the layout may not be supported yet.",
            )
        )
    if any(m.source_status == "ambiguous" for m in measurements):
        warnings.append(
            DocumentWarning(
                code="ambiguous_measurements",
                message="Some results are ambiguous or conflicting. Check them against the original report.",
            )
        )

    text = document.text
    # Metadata only: report contents are never logged.
    logger.info(
        "Extracted report: pages=%d chars=%d measurements=%d warnings=%d elapsed_ms=%.0f",
        document.page_count,
        len(text),
        len(measurements),
        len(warnings),
        (time.perf_counter() - started) * 1000,
    )
    return ExtractionResponse(
        page_count=document.page_count,
        extraction_method=document.method,
        character_count=len(text),
        pages=[PageTextOut(page_number=p.page_number, text=p.text, has_text=p.has_text) for p in document.pages],
        measurements=measurements,
        warnings=warnings,
    )
