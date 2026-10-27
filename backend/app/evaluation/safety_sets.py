"""Measures unsafe-language detection on labelled sentence sets (development and held-out)."""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT
from app.safety.validation import find_unsafe_language

DATASETS = REPO_ROOT / "evaluation" / "datasets"
DEV_SET = DATASETS / "safety_dev.json"
HELDOUT_SET = DATASETS / "safety_heldout.json"
UNSAFE_LABELS = ("diagnostic_language", "treatment_advice", "false_reassurance")

Detector = Callable[[str], list[tuple[str, str, str]]]


def evaluate_safety_set(path: Path, detector: Detector = find_unsafe_language) -> dict[str, Any]:
    raw = path.read_bytes()
    data = json.loads(raw)
    per_label: dict[str, dict[str, Any]] = {
        label: {"n": 0, "flagged_any": 0, "flagged_correct": 0, "missed": []} for label in UNSAFE_LABELS
    }
    safe = {"n": 0, "false_positives": []}
    for item in data["items"]:
        codes = {code for code, _, _ in detector(item["text"])}
        if item["label"] == "safe":
            safe["n"] += 1
            if codes:
                safe["false_positives"].append({"id": item["id"], "text": item["text"], "codes": sorted(codes)})
            continue
        stats = per_label[item["label"]]
        stats["n"] += 1
        stats["flagged_any"] += bool(codes)
        stats["flagged_correct"] += item["label"] in codes
        if not codes:
            stats["missed"].append({"id": item["id"], "text": item["text"]})
    unsafe_n = sum(s["n"] for s in per_label.values())
    for stats in per_label.values():
        stats["recall"] = stats["flagged_any"] / stats["n"] if stats["n"] else None
    return {
        "name": data["name"],
        "split": data["split"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "unsafe_recall": sum(s["flagged_any"] for s in per_label.values()) / unsafe_n if unsafe_n else None,
        "category_accuracy": sum(s["flagged_correct"] for s in per_label.values()) / unsafe_n if unsafe_n else None,
        "false_positive_rate": len(safe["false_positives"]) / safe["n"] if safe["n"] else None,
        "per_label": per_label,
        "safe": safe,
    }
