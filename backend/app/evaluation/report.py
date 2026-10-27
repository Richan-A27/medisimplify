"""Renders evaluation results as Markdown. Every number comes from results.json."""

from typing import Any


def _fmt(value: Any, pct: bool = False) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value * 100:.1f}%" if pct else f"{value:.2f}"
    return str(value)


def render_report(results: dict[str, Any]) -> str:
    cfg = results["config"]
    ds = results["dataset"]
    out = [
        "# MediSimplify evaluation results",
        "",
        f"Run created {results['created']} on dataset **{ds['name']} v{ds['version']}** ({ds['cases']} synthetic cases).",
        f"Annotation: {ds['annotation'].get('annotator', 'n/a')}; review status: {ds['annotation'].get('review_status', 'n/a')}.",
        "",
        "All metrics below are **computed automatically**. Human judgments are reported separately at the end. "
        "With this few cases, differences between strategies are descriptive only; no statistical significance is claimed.",
        "",
        "## Configuration",
        "",
        "| Setting | Value |",
        "| --- | --- |",
    ]
    for key in ("stages", "strategies", "prompt_version", "llm_model", "temperature", "seed", "max_output_tokens",
                "embedding_model", "rag_top_k", "rag_min_similarity"):
        value = cfg.get(key)
        out.append(f"| {key} | {', '.join(value) if isinstance(value, list) else _fmt(value)} |")
    for note in results.get("notes", []):
        out += ["", f"> {note}"]

    if "extraction" in results:
        agg = results["extraction"]["aggregate"]
        m = agg["measurement_micro"]
        out += [
            "", "## 1. Extraction (rule-based parser vs gold annotations)", "",
            f"- Exact-match measurements (name, value, unit, range, flag): precision {_fmt(m['precision'], True)}, "
            f"recall {_fmt(m['recall'], True)} over {agg['gold_measurements']} gold measurements.",
            f"- Expected PDF failures reported with the correct error: {agg['failure_cases_with_expected_error']}/{agg['failure_cases']}; "
            f"unexpected errors: {agg['unexpected_errors']}.",
            "", "| Case | Precision | Recall | Missed | Abnormal-candidate recall | Ambiguity recall | Error |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for case_id, row in results["extraction"]["per_case"].items():
            if "error" in row:
                out.append(f"| {case_id} | | | | | | {row['error']} (expected {row['expected_error']}) |")
            else:
                out.append(
                    f"| {case_id} | {_fmt(row['measurements']['precision'], True)} | {_fmt(row['measurements']['recall'], True)} | "
                    f"{', '.join(row['missed']) or '-'} | {_fmt(row['abnormal_candidates']['recall'], True)} | "
                    f"{_fmt(row['ambiguity']['recall'], True)} | |"
                )

    if "retrieval" in results:
        out += ["", "## 2. Retrieval (real index and embedding model)", ""]
        if "skipped" in results["retrieval"]:
            out.append(f"Skipped: {results['retrieval']['skipped']}")
        else:
            agg = results["retrieval"]["aggregate"]
            out += [
                f"- Tests covered by the corpus: {agg['covered_tests']}. Top-1 source accuracy {_fmt(agg['top1_accuracy'], True)}; "
                f"expected source anywhere in top-{agg['top_k']}: {_fmt(agg['hit_rate_at_k'], True)}.",
                f"- Tests not covered by the corpus: {agg['uncovered_tests']}. Correctly given no evidence: {_fmt(agg['abstention_rate'], True)}.",
                f"- Threshold {agg['min_similarity']}, model `{agg['embedding_model']}`.",
                "", "| Case | Test | Expected source(s) | Retrieved sources | Correct |", "| --- | --- | --- | --- | --- |",
            ]
            for case_id, row in results["retrieval"]["per_case"].items():
                for t in row["per_test"]:
                    correct = t.get("top1_correct", t.get("abstained"))
                    expected = ", ".join(s.removeprefix("medlineplus-") for s in t["expected"]) or "(none: should abstain)"
                    retrieved = ", ".join(s.removeprefix("medlineplus-") for s in t["retrieved"]) or "(none)"
                    out.append(f"| {case_id} | {t['test']} | {expected} | {retrieved} | {'yes' if correct else '**no**'} |")

    if "validator" in results:
        agg = results["validator"]["aggregate"]
        out += [
            "", "## 3. Safety validator: controlled fault injection", "",
            "Correct reference outputs were built from each case's facts, then one fault was injected at a time. "
            "'Detected' means the validator raised the matching issue; 'blocked' means the summary was marked failed. "
            "Fault sentences were written by the project, so these rates describe these faults only, not real model errors.",
            "",
            f"- Clean reference outputs passing with no issues: {agg['clean_outputs_passed']}/{agg['clean_outputs']}"
            + (f" (issues: {agg['clean_issue_codes']})" if agg["clean_issue_codes"] else "") + ".",
            "", "| Fault | Kind | Wording | Applicable | Detected | Blocked | Missed in |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for name, s in results["validator"]["per_fault"].items():
            out.append(
                f"| {name} | {s['kind']} | {s['wording']} | {s['applicable']} | {s['detected']} ({_fmt(s['detection_rate'], True)}) | "
                f"{s['blocked']} | {', '.join(s['missed_cases']) or '-'} |"
            )

    if "safety_language" in results:
        out += [
            "", "## 3b. Safety-language detection on labelled sentence sets", "",
            "The development set was used to design the detector; the held-out set was written and frozen before any "
            "change and is only measured. Both were written by the same author (an AI assistant), so held-out results "
            "are likely optimistic.",
            "", "| Set | SHA-256 | Unsafe detected | Diagnosis | Treatment | Reassurance | Safe sentences flagged |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for split in ("dev", "heldout"):
            r = results["safety_language"][split]
            pl = r["per_label"]
            unsafe_n = sum(v["n"] for v in pl.values())
            detected = sum(v["flagged_any"] for v in pl.values())
            out.append(
                f"| {split} | `{r['sha256'][:12]}` | {detected}/{unsafe_n} ({_fmt(r['unsafe_recall'], True)}) | "
                + " | ".join(f"{pl[k]['flagged_any']}/{pl[k]['n']}" for k in ("diagnostic_language", "treatment_advice", "false_reassurance"))
                + f" | {len(r['safe']['false_positives'])}/{r['safe']['n']} |"
            )
        held = results["safety_language"]["heldout"]
        misses = [m["text"] for v in held["per_label"].values() for m in v["missed"]]
        if misses:
            out += ["", "Held-out misses:"] + [f"- {t}" for t in misses]
        if held["safe"]["false_positives"]:
            out += ["", "Held-out false positives:"] + [f"- {fp['text']}" for fp in held["safe"]["false_positives"]]

    if "llm" in results:
        out += ["", "## 4. Prompting strategies (LLM)", ""]
        if "skipped" in results["llm"]:
            out.append(f"**Not run.** {results['llm']['skipped']}")
        else:
            strategies = list(results["llm"]["per_strategy"])
            rows = [
                ("Cases scored / attempted", lambda a: f"{a['completed']}/{a['cases']}"),
                ("LLM errors", lambda a: ", ".join(a["llm_errors"]) or "-"),
                ("Validation passed / warnings / failed", lambda a: "/".join(str(a["status_counts"][k]) for k in ("passed", "passed_with_warnings", "failed"))),
                ("Value preservation (mean)", lambda a: _fmt(a["mean_value_preservation"], True)),
                ("Value/unit/range/test errors (total)", lambda a: _fmt(a["total_value_errors"])),
                ("Test coverage (mean)", lambda a: _fmt(a["mean_test_coverage"], True)),
                ("Abnormality recall / precision", lambda a: f"{_fmt(a['mean_abnormality_recall'], True)} / {_fmt(a['mean_abnormality_precision'], True)}"),
                ("Uncited background per explanation", lambda a: _fmt(a["mean_unsupported_background_per_explanation"])),
                ("Unverified numbers (total)", lambda a: _fmt(a["total_unverified_numbers"])),
                ("Citation validity / relevance", lambda a: f"{_fmt(a['mean_citation_validity'], True)} / {_fmt(a['mean_citation_relevance'], True)}"),
                ("Safety-language failures (total)", lambda a: _fmt(a["total_safety_failures"])),
                ("Flesch-Kincaid grade (mean)", lambda a: _fmt(a["mean_fk_grade"])),
                ("Flesch reading ease (mean)", lambda a: _fmt(a["mean_reading_ease"])),
                ("Latency ms (mean)", lambda a: _fmt(a["mean_latency_ms"])),
                ("Prompt / output tokens (mean)", lambda a: f"{_fmt(a['mean_prompt_tokens'])} / {_fmt(a['mean_output_tokens'])}"),
            ]
            out += ["| Metric | " + " | ".join(strategies) + " |", "| --- |" + " --- |" * len(strategies)]
            for label, fn in rows:
                out.append(f"| {label} | " + " | ".join(fn(results["llm"]["per_strategy"][s]["aggregate"]) for s in strategies) + " |")
            if results["llm"].get("replay_prompt_mismatches"):
                out += ["", f"Replay warning: prompts changed since recording for {results['llm']['replay_prompt_mismatches']}."]

    out += ["", "## 5. Human judgments", ""]
    human = results.get("human", {})
    if human.get("status") == "not collected":
        out.append("Not collected yet. Fill in `human_ratings.csv` from an LLM run (strategy names are hidden; see "
                   "`rating_items.md`) and re-run with `--human-ratings` and `--rating-key`.")
    else:
        out += [f"Raters: {human['raters']}.", "", "| Strategy | Factual accuracy | Clarity | Completeness | Rated safe |",
                "| --- | --- | --- | --- | --- |"]
        for strategy, m in human["per_strategy"].items():
            out.append(
                f"| {strategy} | {_fmt(m['factual_accuracy']['mean'])} (n={m['factual_accuracy']['n']}) | {_fmt(m['clarity']['mean'])} | "
                f"{_fmt(m['completeness']['mean'])} | {_fmt(m['safe']['mean'], True)} |"
            )
    return "\n".join(out) + "\n"
