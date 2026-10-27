"""Rule-based validation of LLM summaries against the report facts and retrieved evidence.

Errors mean the output must not be shown as-is; warnings are shown alongside it. These are heuristic
checks: they catch common failures (changed values, invented citations, diagnostic or reassuring
language) but cannot prove an explanation is medically correct.
"""

import re
from collections.abc import Iterable

from app.safety.language import (
    find_unsafe_sentences,
    is_conditional_statement,
    is_limitation_statement,
    split_sentences,
)
from app.schemas.evidence import EvidencePassage, TestEvidence
from app.schemas.report import Measurement
from app.schemas.summary import Strategy, SummaryOutput, ValidationIssue, ValidationReport

CHECKS = (
    "test_coverage",
    "value_preservation",
    "citation_validity",
    "citation_relevance",
    "evidence_support",
    "number_grounding",
    "abnormality_consistency",
    "safety_language",
    "required_fields",
)

_CONDITION = (
    r"(?:disease|disorder|condition|infection|cancer|diabetes|prediabetes|failure|deficiency|"
    r"\w+(?:emia|itis|osis|ism|pathy))"
)
DIAGNOSIS_PATTERNS = [
    rf"\byou (?:\w+ ){{0,2}}(?:have|has|are suffering from|suffer from|are diagnosed with|are at risk (?:of|for))\b"
    rf"[^.]{{0,40}}?\b{_CONDITION}\b",
    r"\b(?:this|these results?|your results?|the results?|it) (?:means?|indicates?|confirms?|shows?|proves?) "
    r"(?:that )?you (?:have|are)\b",
    r"\byou (?:are|have been) diagnosed\b",
]
TREATMENT_PATTERNS = [
    r"\byou (?:should|need to|must|ought to) (?:take|start|stop|increase|decrease|reduce|avoid|eat|use|begin)\b",
    r"\b(?:take|start taking|stop taking|increase|reduce|decrease) (?:your |more |less |an? )?"
    r"(?:medication|medicine|dose|dosage|supplements?|insulin|iron|vitamin|statins?|pills?)\b",
    r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|iu)\b(?!\s*/)",
    r"\bprescri(?:be|ption)\b",
]
REASSURANCE_PATTERNS = [
    r"\b(?:your|these|all|the|all your|all of your) (?:test |lab )?results? (?:are|is|look|looks|seem|seems) "
    r"(?:all |completely |perfectly )?(?:normal|fine|good|healthy|okay|ok|reassuring)\b",
    r"\byou are (?:perfectly |completely )?(?:healthy|fine|in good health|normal)\b",
    r"\bnothing to (?:worry|be concerned) about\b",
    r"\bno (?:need|reason) to (?:worry|see|consult|follow up)\b",
    r"\bperfectly healthy\b",
]
_SAFETY_GROUPS = (
    ("diagnostic_language", DIAGNOSIS_PATTERNS, "States or implies a diagnosis."),
    ("treatment_advice", TREATMENT_PATTERNS, "Gives treatment or medication advice."),
    ("false_reassurance", REASSURANCE_PATTERNS, "Claims results are normal or healthy."),
)
_SAFETY_RES = [(code, [re.compile(p, re.IGNORECASE) for p in pats], msg) for code, pats, msg in _SAFETY_GROUPS]

def find_unsafe_language(text: str) -> list[tuple[str, str, str]]:
    """Return (code, message, matched text) for each unsafe-language category found in `text`.

    Combines the explicit keyword patterns above with the sentence-level detector in language.py.
    """
    found: dict[str, tuple[str, str, str]] = {}
    for sentence in split_sentences(text):
        for code, patterns, message in _SAFETY_RES:
            if code in found or (code != "treatment_advice" and is_limitation_statement(sentence)):
                continue
            if code == "diagnostic_language" and is_conditional_statement(sentence):
                continue
            for pattern in patterns:
                match = pattern.search(sentence)
                if match:
                    found[code] = (code, message, match.group(0))
                    break
    for code, message, sentence in find_unsafe_sentences(text):
        found.setdefault(code, (code, message, sentence))
    return list(found.values())


_NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")
_CITATION_TOKEN_RE = re.compile(r"\[?\bE\d+\b\]?")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
# Words that mark a sentence as describing the report itself rather than general medical background.
_REPORT_WORDS = re.compile(
    r"\b(?:your result|your value|your report|the report|printed|reference range|range|flag|flagged|"
    r"not printed|lab did|laboratory|result is|value is)\b",
    re.IGNORECASE,
)
_PROFESSIONAL_RE = re.compile(r"\b(?:doctor|healthcare|health care|provider|clinician|professional)\b", re.I)
MAX_FREE_INTEGER = 10  # small counts ("two tests", "3 questions") are not treated as clinical numbers


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def _texts(output: SummaryOutput) -> Iterable[tuple[str, str]]:
    yield "summary", output.summary
    for i, item in enumerate(output.test_explanations):
        yield f"test_explanations[{i}].explanation", item.explanation
    for i, item in enumerate(output.reported_abnormalities):
        yield f"reported_abnormalities[{i}].description", item.description
    for i, text in enumerate(output.uncertainties):
        yield f"uncertainties[{i}]", text
    for i, text in enumerate(output.questions_for_doctor):
        yield f"questions_for_doctor[{i}]", text


def _numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(_CITATION_TOKEN_RE.sub(" ", text)))


def _canonical(number: str) -> str:
    return number.rstrip("0").rstrip(".") if "." in number else number.lstrip("0") or "0"


def validate_summary(
    output: SummaryOutput,
    measurements: list[Measurement],
    strategy: Strategy,
    evidence: list[EvidencePassage],
    test_evidence: list[TestEvidence],
) -> ValidationReport:
    issues: list[ValidationIssue] = []

    def add(code: str, severity: str, message: str, location: str | None = None) -> None:
        issues.append(ValidationIssue(code=code, severity=severity, message=message, location=location))  # type: ignore[arg-type]

    facts: dict[str, list[Measurement]] = {}
    for m in measurements:
        facts.setdefault(_key(m.test_name), []).append(m)
    passages = {p.citation_id: p for p in evidence}
    retrieved_for = {_key(t.test_name): set(t.citation_ids) for t in test_evidence}

    # test_coverage + value_preservation
    explained: set[str] = set()
    for i, item in enumerate(output.test_explanations):
        loc = f"test_explanations[{i}]"
        candidates = facts.get(_key(item.test_name))
        if not candidates:
            add("unknown_test", "error", f"'{item.test_name}' is not a test in the report.", loc)
            continue
        explained.add(_key(item.test_name))
        match = next((m for m in candidates if _norm(m.value) == _norm(item.reported_value)), None)
        if match is None:
            add("value_mismatch", "error", f"{item.test_name}: value '{item.reported_value}' differs from the report.", loc)
            continue
        if _norm(match.unit) != _norm(item.unit):
            add("unit_mismatch", "error", f"{item.test_name}: unit '{item.unit}' differs from the report ('{match.unit}').", loc)
        if _norm(match.reference_range) != _norm(item.reference_range):
            add(
                "range_mismatch",
                "error",
                f"{item.test_name}: range '{item.reference_range}' differs from the report ('{match.reference_range}').",
                loc,
            )
    for name, group in facts.items():
        if name not in explained:
            add("missing_test_explanation", "warning", f"No explanation for '{group[0].test_name}'.")

    # citation_validity + citation_relevance + evidence_support
    allow_citations = strategy == "rag"
    cited_ids: set[str] = set()
    for i, item in enumerate(output.test_explanations):
        loc = f"test_explanations[{i}]"
        for cid in item.citation_ids:
            cited_ids.add(cid)
            if not allow_citations or cid not in passages:
                add("invalid_citation", "error", f"Citation '{cid}' does not match any provided passage.", loc)
            elif cid not in retrieved_for.get(_key(item.test_name), set()):
                add("citation_not_for_test", "warning", f"{cid} was not retrieved for {item.test_name}.", loc)
        background = [s for s in _SENTENCE_RE.split(item.explanation) if s.strip() and not _REPORT_WORDS.search(s)]
        if background and not item.citation_ids:
            add(
                "unsupported_background",
                "warning",
                f"{item.test_name}: {len(background)} background sentence(s) without a cited source.",
                loc,
            )
    for i, citation in enumerate(output.evidence_citations):
        cited_ids.add(citation.citation_id)
        if not allow_citations or citation.citation_id not in passages:
            add(
                "invalid_citation",
                "error",
                f"Citation '{citation.citation_id}' does not match any provided passage.",
                f"evidence_citations[{i}]",
            )
    for location, text in _texts(output):
        for token in re.findall(r"\bE\d+\b", text):
            if not allow_citations or token not in passages:
                add("invalid_citation", "error", f"Text refers to unknown source '{token}'.", location)

    # number_grounding
    allowed_numbers: set[str] = set()
    for m in measurements:
        for text in (m.value, m.reference_range or "", m.unit or "", m.test_name):
            allowed_numbers |= {_canonical(n) for n in _numbers(text)}
    for cid in cited_ids:
        if cid in passages:
            allowed_numbers |= {_canonical(n) for n in _numbers(passages[cid].text)}
    for location, text in _texts(output):
        for number in _numbers(text):
            canonical = _canonical(number)
            if canonical in allowed_numbers:
                continue
            if "." not in number and int(number) <= MAX_FREE_INTEGER:
                continue
            add("unverified_number", "warning", f"Number '{number}' is not in the report or cited sources.", location)

    # abnormality_consistency
    expected: dict[str, str] = {}
    for m in measurements:
        if m.reported_flag:
            expected[_key(m.test_name)] = "report_flag"
        elif m.range_comparison in ("above_range", "below_range"):
            expected.setdefault(_key(m.test_name), "range_comparison")
    listed: set[str] = set()
    for i, item in enumerate(output.reported_abnormalities):
        loc = f"reported_abnormalities[{i}]"
        key = _key(item.test_name)
        listed.add(key)
        if key not in facts:
            add("unknown_test", "error", f"Abnormality lists '{item.test_name}', which is not in the report.", loc)
        elif key not in expected:
            add(
                "unsupported_abnormality",
                "error",
                f"{item.test_name} is listed as abnormal but is neither flagged nor outside its printed range.",
                loc,
            )
        elif expected[key] != item.basis:
            add("abnormality_basis_mismatch", "warning", f"{item.test_name}: basis should be '{expected[key]}'.", loc)
    for key, basis in expected.items():
        if key not in listed:
            add("missed_abnormality", "warning", f"{facts[key][0].test_name} ({basis}) is not listed as abnormal.")

    # safety_language
    for location, text in _texts(output):
        for code, message, found in find_unsafe_language(text):
            severity = "warning" if location.startswith("questions_for_doctor") else "error"
            add(code, severity, f"{message} Found: \"{found}\".", location)

    # required_fields
    if not output.summary.strip():
        add("empty_summary", "error", "The summary is empty.", "summary")
    if not output.safety_notice.strip() or not _PROFESSIONAL_RE.search(output.safety_notice):
        add("weak_safety_notice", "warning", "The safety notice does not refer the reader to a professional.", "safety_notice")
    if not output.questions_for_doctor:
        add("no_questions", "warning", "No questions for a healthcare professional were provided.", "questions_for_doctor")

    if any(i.severity == "error" for i in issues):
        status = "failed"
    elif issues:
        status = "passed_with_warnings"
    else:
        status = "passed"
    return ValidationReport(status=status, issues=issues, checks_run=list(CHECKS))
