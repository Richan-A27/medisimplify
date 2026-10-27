"""Run the MediSimplify evaluation.

From the repository root:

    backend/.venv/bin/python evaluation/scripts/run_evaluation.py                 # all stages
    backend/.venv/bin/python evaluation/scripts/run_evaluation.py --stages extraction retrieval validator
    backend/.venv/bin/python evaluation/scripts/run_evaluation.py --stages llm --delay 6
    backend/.venv/bin/python evaluation/scripts/run_evaluation.py --stages llm --replay evaluation/results/<run>/responses

Results go to evaluation/results/<run-id>/ (results.json, report.md and, after an LLM run, the saved
responses and a blinded human-rating sheet). The LLM stage needs GEMINI_API_KEY unless --replay is used.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.evaluation.dataset import DEFAULT_DATASET, load_dataset  # noqa: E402
from app.evaluation.report import render_report  # noqa: E402
from app.evaluation.runner import STAGES, ReplayLLM, RunConfig, run_evaluation  # noqa: E402
from app.rag.service import KnowledgeBase  # noqa: E402
from app.schemas.summary import STRATEGIES  # noqa: E402
from app.api.reports import get_llm  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stages", nargs="+", choices=STAGES, default=list(STAGES))
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=list(STRATEGIES))
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--run-id", help="Output folder name (default: timestamp)")
    parser.add_argument("--replay", type=Path, help="Re-score saved responses instead of calling the API")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds between LLM calls (free-tier rate limits)")
    parser.add_argument("--human-ratings", type=Path, help="Completed human_ratings.csv")
    parser.add_argument("--rating-key", type=Path, help="rating_key.json from the same LLM run")
    args = parser.parse_args()

    settings = get_settings()
    dataset = load_dataset(args.dataset)
    knowledge_base = KnowledgeBase(settings)

    llm, reason = None, None
    notes: list[str] = []
    if "llm" in args.stages:
        if args.replay:
            llm = ReplayLLM(args.replay)
            notes.append(f"LLM stage replayed saved responses from {args.replay}.")
        else:
            llm = get_llm(settings)
            if llm is None:
                reason = "GEMINI_API_KEY is not set, so no model outputs were generated. No LLM results are reported."

    from datetime import datetime, UTC

    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "evaluation" / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    results = run_evaluation(
        dataset,
        settings,
        RunConfig(
            stages=tuple(args.stages),
            strategies=tuple(args.strategies),
            out_dir=out_dir,
            llm_delay_seconds=args.delay,
            human_ratings=args.human_ratings,
            rating_key=args.rating_key,
            notes=notes,
        ),
        llm=llm,
        llm_unavailable_reason=reason,
        get_retriever=knowledge_base.retriever,
    )
    (out_dir / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    (out_dir / "report.md").write_text(render_report(results))
    print(f"Wrote {out_dir.relative_to(REPO_ROOT)}/results.json and report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
