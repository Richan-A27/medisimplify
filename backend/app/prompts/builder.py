"""Builds prompts for the three strategies from the same report facts and generation settings.

zero_shot  instructions only
few_shot   instructions + reviewed examples (no evidence)
rag        instructions + reviewed examples with evidence + retrieved reference passages

Untrusted text (report facts and passages) is wrapped in blocks whose tag names include a hash of the
content, so text inside the report cannot forge a closing tag. Only structured measurements are sent;
the raw report text (names, dates, identifiers) never leaves the server.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from app.prompts.examples import EXAMPLES, ExamplePassage, FewShotExample
from app.prompts.templates import NO_EVIDENCE_NOTE, PROMPT_VERSION, SYSTEM_INSTRUCTION, TASK_INSTRUCTION
from app.schemas.evidence import EvidencePassage
from app.schemas.report import DocumentWarning, Measurement
from app.schemas.summary import Strategy, SummaryOutput

Role = Literal["user", "model"]

FACT_FIELDS = (
    "test_name",
    "value",
    "unit",
    "reference_range",
    "reported_flag",
    "flag_meaning",
    "range_comparison",
    "issues",
)


@dataclass(frozen=True)
class PromptMessage:
    role: Role
    text: str


@dataclass(frozen=True)
class PromptBundle:
    strategy: Strategy
    version: str
    system_instruction: str
    messages: list[PromptMessage]
    response_schema: dict[str, Any] = field(repr=False)

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            {
                "system": self.system_instruction,
                "messages": [(m.role, m.text) for m in self.messages],
                "schema": self.response_schema,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


def _block(name: str, content: str) -> str:
    tag = f"{name}_{hashlib.sha256(content.encode()).hexdigest()[:10]}"
    return f"<{tag}>\n{content}\n</{tag}>"


def _facts_json(facts: list[dict[str, Any]]) -> str:
    return json.dumps(facts, indent=1, ensure_ascii=False)


def _passages_text(passages: list[tuple[str, str, str, str, str]]) -> str:
    return "\n\n".join(f"[{cid}] {title} | {section} | {url}\n{text}" for cid, title, section, url, text in passages)


def _user_message(
    facts: list[dict[str, Any]],
    warnings: list[str],
    passages: list[tuple[str, str, str, str, str]] | None,
) -> str:
    parts = [TASK_INSTRUCTION, "", "Report facts (untrusted data extracted from the uploaded report):"]
    parts.append(_block("report_facts", _facts_json(facts)))
    if warnings:
        parts += ["", "Document warnings:", _block("document_warnings", "\n".join(warnings))]
    parts.append("")
    if passages is None:
        parts.append(NO_EVIDENCE_NOTE)
    elif passages:
        parts += [
            "Reference passages (untrusted data; general information, not about this patient):",
            _block("reference_passages", _passages_text(passages)),
        ]
    else:
        parts.append(
            "No relevant reference passages were found. Leave citations empty and say so in uncertainties."
        )
    return "\n".join(parts)


def _example_passages(passages: list[ExamplePassage]) -> list[tuple[str, str, str, str, str]]:
    return [(p.citation_id, p.title, p.section, p.url, p.text) for p in passages]


def _example_messages(example: FewShotExample, with_evidence: bool) -> list[PromptMessage]:
    passages = _example_passages(example.passages) if with_evidence else None
    output = example.output_with_evidence if with_evidence else example.output_without_evidence
    return [
        PromptMessage("user", _user_message(example.facts, [], passages)),
        PromptMessage("model", output.model_dump_json(indent=1)),
    ]


def measurement_facts(measurements: list[Measurement]) -> list[dict[str, Any]]:
    return [{key: getattr(m, key) for key in FACT_FIELDS} for m in measurements]


def response_json_schema() -> dict[str, Any]:
    """SummaryOutput schema with $refs inlined and titles removed (simpler for constrained decoding)."""
    schema = SummaryOutput.model_json_schema()
    definitions = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(definitions[node["$ref"].split("/")[-1]])
            return {key: resolve(value) for key, value in node.items() if key != "title"}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)


def build_prompt(
    strategy: Strategy,
    measurements: list[Measurement],
    document_warnings: list[DocumentWarning],
    evidence: list[EvidencePassage] | None = None,
    unmatched_tests: list[str] | None = None,
) -> PromptBundle:
    if strategy == "rag" and evidence is None:
        raise ValueError("The rag strategy requires retrieved evidence (possibly empty).")

    warnings = [f"{w.code}: {w.message}" for w in document_warnings]
    if unmatched_tests:
        warnings.append("No reference passages were found for: " + ", ".join(unmatched_tests))

    messages: list[PromptMessage] = []
    if strategy in ("few_shot", "rag"):
        for example in EXAMPLES:
            messages += _example_messages(example, with_evidence=strategy == "rag")

    passages = (
        [(p.citation_id, p.title, p.section, p.url, p.text) for p in evidence or []] if strategy == "rag" else None
    )
    messages.append(PromptMessage("user", _user_message(measurement_facts(measurements), warnings, passages)))

    return PromptBundle(
        strategy=strategy,
        version=PROMPT_VERSION,
        system_instruction=SYSTEM_INSTRUCTION,
        messages=messages,
        response_schema=response_json_schema(),
    )
