"""Write /api/reports/summarize responses used by the frontend end-to-end tests.

Usage (from backend/):  .venv/bin/python -m scripts.generate_e2e_fixtures

These are TEST FIXTURES ONLY. They run the real pipeline (extraction, retrieval, prompt building and
validation) but replace Gemini with a scripted client that returns a mechanically built answer, so the
UI can be tested without an API key. The application itself never uses scripted responses.
"""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.reports import get_llm
from app.config import get_settings
from app.evaluation.reference import reference_output
from app.main import create_app
from app.prompts.builder import PromptBundle
from app.schemas.evidence import TestEvidence
from app.schemas.report import Measurement
from app.schemas.summary import TokenUsage
from app.services.llm import LLMResult
from scripts.synthetic_reports import REPORTS, text_pdf

OUT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "fixtures"
_FACTS_RE = re.compile(r"<(report_facts_[0-9a-f]+)>\n(.*?)\n</\1>", re.S)
_PASSAGE_RE = re.compile(r"^\[(E\d+)\] ([^|\n]+) \|[^\n]*\n([^\n]*)", re.M)


class ScriptedLLM:
    model = "scripted-test-model"

    def __init__(self, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def generate(self, prompt: PromptBundle) -> LLMResult:
        final = prompt.messages[-1].text
        facts = json.loads(_FACTS_RE.search(final).group(2))  # type: ignore[union-attr]
        measurements = [
            Measurement(**f, value_numeric=None, source_status="complete", page_number=1, source_line="") for f in facts
        ]
        passages = _PASSAGE_RE.findall(final)
        evidence = [
            TestEvidence(
                test_name=m.test_name,
                query="",
                citation_ids=[c for c, title, text in passages if m.test_name.split(",")[0].lower() in (title + text).lower()][:1],
            )
            for m in measurements
        ]
        output = reference_output(measurements, evidence)
        if self.unsafe:
            output.summary += " Your results are normal and there is nothing to worry about."
            output.test_explanations[0].reported_value = "999"
        return LLMResult(text=output.model_dump_json(), model=self.model,
                         usage=TokenUsage(prompt_tokens=2400, output_tokens=650, total_tokens=3050), latency_ms=4200)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, unsafe in (("summary-passed", False), ("summary-failed", True)):
        app = create_app(get_settings())
        app.dependency_overrides[get_llm] = lambda unsafe=unsafe: ScriptedLLM(unsafe)
        response = TestClient(app).post(
            "/api/reports/summarize",
            files={"file": ("r.pdf", text_pdf([REPORTS["metabolic_abnormal"]]), "application/pdf")},
            data={"strategy": "rag"},
        )
        response.raise_for_status()
        body = response.json()
        (OUT_DIR / f"{name}.json").write_text(json.dumps(body, indent=1) + "\n")
        print(f"wrote {name}.json: validation={body['validation']['status']}, passages={len(body['evidence'])}")


if __name__ == "__main__":
    main()
