"""Fake LLM clients for tests. They never call a network service."""

__all__ = ["FakeLLM", "facts_from_prompt", "passages_for", "safe_output"]

import json
import re
from collections.abc import Callable

from app.prompts.builder import PromptBundle
from app.evaluation.reference import reference_output as safe_output
from app.evaluation.reference import synthetic_passages as passages_for
from app.schemas.evidence import TestEvidence
from app.schemas.report import Measurement
from app.schemas.summary import TokenUsage
from app.services.llm import LLMError, LLMResult

_FACTS_RE = re.compile(r"<(report_facts_[0-9a-f]+)>\n(.*?)\n</\1>", re.S)
_PASSAGE_RE = re.compile(r"^\[(E\d+)\] ([^|\n]+) \|[^\n]*\n([^\n]*)", re.M)


def facts_from_prompt(prompt: PromptBundle) -> list[dict]:
    match = _FACTS_RE.search(prompt.messages[-1].text)
    assert match, "report facts block missing from prompt"
    return json.loads(match.group(2))


class FakeLLM:
    """Returns a scripted response. `respond` receives the prompt so tests can echo the facts."""

    def __init__(self, respond: Callable[[PromptBundle], str] | None = None, error: LLMError | None = None) -> None:
        self.model = "fake-model"
        self.respond = respond or self._safe_response
        self.error = error
        self.prompts: list[PromptBundle] = []

    @staticmethod
    def _safe_response(prompt: PromptBundle) -> str:
        measurements = [
            Measurement(
                **fact, value_numeric=None, source_status="complete", page_number=1, source_line=""
            )
            for fact in facts_from_prompt(prompt)
        ]
        passages = _PASSAGE_RE.findall(prompt.messages[-1].text)
        # Cite a passage only when it mentions the test, as a careful model would.
        evidence = [
            TestEvidence(
                test_name=m.test_name,
                query="",
                citation_ids=[cid for cid, title, text in passages if m.test_name.split(",")[0].lower() in (title + text).lower()][:1],
            )
            for m in measurements
        ]
        return safe_output(measurements, evidence if passages else None).model_dump_json()

    def generate(self, prompt: PromptBundle) -> LLMResult:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return LLMResult(
            text=self.respond(prompt),
            model=self.model,
            usage=TokenUsage(prompt_tokens=100, output_tokens=50, total_tokens=150),
            latency_ms=5,
        )
