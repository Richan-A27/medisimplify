import json

import pytest

from app.evaluation.safety_sets import DEV_SET, HELDOUT_SET, evaluate_safety_set
from app.safety.language import find_unsafe_sentences
from app.safety.validation import find_unsafe_language

# Recorded when the held-out set was frozen, before any validator change. If this fails, the held-out set
# was edited: restore it, or add a new versioned file and report results on that instead.
HELDOUT_SHA256 = "5533fba4c4f88d356eda5f97dbd73e3eb0e346ba7f85f83a0e764ecdb0443a7b"

DEV = json.loads(DEV_SET.read_text())["items"]


def codes(text: str) -> set[str]:
    return {code for code, _, _ in find_unsafe_language(text)}


def test_heldout_set_is_frozen_and_separate_from_dev() -> None:
    result = evaluate_safety_set(HELDOUT_SET)

    assert result["sha256"] == HELDOUT_SHA256
    held = {i["text"].lower() for i in json.loads(HELDOUT_SET.read_text())["items"]}
    assert not held & {i["text"].lower() for i in DEV}


@pytest.mark.parametrize("item", [i for i in DEV if i["label"] != "safe"], ids=lambda i: i["id"])
def test_dev_unsafe_sentences_are_flagged_in_their_category(item: dict) -> None:
    assert item["label"] in codes(item["text"])


@pytest.mark.parametrize("item", [i for i in DEV if i["label"] == "safe"], ids=lambda i: i["id"])
def test_dev_safe_sentences_are_not_flagged(item: dict) -> None:
    assert codes(item["text"]) == set()


@pytest.mark.parametrize(
    "text",
    [
        "This does not mean you have a disease.",
        "Being inside the range does not mean you are healthy.",
        "A single result cannot show whether you have a condition.",
        "If your hemoglobin levels are abnormal, it may be a sign that you have a blood disorder.",
        "High cholesterol can increase the risk of heart disease.",
        "Vitamin D helps your body absorb calcium.",
        "Sodium is 140 mmol/L, which is inside the normal range printed on the report.",
    ],
)
def test_limitations_conditionals_and_general_background_are_allowed(text: str) -> None:
    assert codes(text) == set()


def test_each_category_reported_once_with_the_offending_sentence() -> None:
    text = "Your glucose suggests you have diabetes. Your sugar points to diabetes too. Eat less sugar to lower it."

    found = find_unsafe_sentences(text)

    assert [code for code, _, _ in found] == ["diagnostic_language", "treatment_advice"]
    assert found[0][2] == "Your glucose suggests you have diabetes."


def test_heldout_measurement_runs() -> None:
    result = evaluate_safety_set(HELDOUT_SET)

    assert result["split"] == "heldout"
    assert result["unsafe_recall"] is not None and result["false_positive_rate"] is not None
