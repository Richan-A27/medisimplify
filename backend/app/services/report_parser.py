"""Rule-based identification of lab measurements in extracted report text.

The parser is deliberately conservative: it only reports values that appear on one line together
with a test name, copies text exactly as printed, and records issues instead of guessing. Lines it
cannot interpret are skipped rather than reconstructed.
"""

import re
from collections import defaultdict

from app.schemas.report import (
    FlagMeaning,
    Measurement,
    MeasurementIssue,
    RangeComparison,
    SourceStatus,
)
from app.services.pdf_extraction import PageText

NUMBER = r"\d+(?:\.\d+)?"

LINE_RE = re.compile(
    rf"""^\s*
    (?P<name>[A-Za-z][A-Za-z0-9 ,'()/+\-.]*?)\s*:?\s+
    (?P<value>(?:[<>]=?|[≤≥])\s?{NUMBER}|{NUMBER})(?=\s|$)
    (?P<rest>.*)$""",
    re.VERBOSE,
)
INTERVAL_RE = re.compile(rf"(?P<lo>{NUMBER})\s*(?:-|–|—|to)\s*(?P<hi>{NUMBER})")
BOUND_RE = re.compile(rf"(?P<op><=|>=|[<>≤≥])\s*(?P<bound>{NUMBER})")

FLAGS: dict[str, FlagMeaning] = {
    "H": "high",
    "HI": "high",
    "HIGH": "high",
    "L": "low",
    "LO": "low",
    "LOW": "low",
    "HH": "critical",
    "LL": "critical",
    "CRITICAL": "critical",
    "A": "abnormal",
    "ABNORMAL": "abnormal",
}

# Lines starting with these words describe the patient or document, not a test.
NON_TEST_PREFIXES = (
    "age", "dob", "date", "time", "patient", "name", "id", "mrn", "phone", "tel", "fax", "page",
    "sex", "gender", "report", "collected", "received", "reported", "printed", "specimen", "accession",
    "lab no", "sample", "ref", "reference", "doctor", "physician", "address", "zip", "room", "bed",
)
MAX_NAME_WORDS = 6

AMBIGUOUS_ISSUES: set[MeasurementIssue] = {
    "multiple_ranges_found",
    "flag_conflicts_with_range",
    "duplicate_test_conflicting_values",
    "unrecognized_text",
}


def parse_measurements(pages: list[PageText]) -> list[Measurement]:
    measurements = [
        measurement
        for page in pages
        for line in page.text.splitlines()
        if (measurement := parse_line(line, page.page_number)) is not None
    ]
    _mark_conflicting_duplicates(measurements)
    return measurements


def parse_line(line: str, page_number: int) -> Measurement | None:
    match = LINE_RE.match(line)
    if not match:
        return None

    name = " ".join(match["name"].split()).rstrip(" :,-")
    if not _looks_like_test_name(name):
        return None

    value_text = match["value"].replace(" ", "")
    rest = match["rest"].strip()
    issues: list[MeasurementIssue] = []

    reference_range, bounds, rest = _extract_range(rest, issues)
    reported_flag, flag_meaning, remaining = _extract_flag(rest.split())

    unit = remaining[0] if remaining else None
    if len(remaining) > 2:
        return None  # prose containing a number, not a result row
    if len(remaining) == 2:
        issues.append("unrecognized_text")
    if unit is None:
        issues.append("missing_unit")
    if reference_range is None:
        issues.append("missing_reference_range")

    value_numeric = _to_float(value_text)
    if value_numeric is None:
        issues.append("value_is_bound")

    comparison = _compare(value_numeric, bounds)
    if (flag_meaning == "high" and comparison == "below_range") or (
        flag_meaning == "low" and comparison == "above_range"
    ):
        issues.append("flag_conflicts_with_range")

    return Measurement(
        test_name=name,
        value=value_text,
        value_numeric=value_numeric,
        unit=unit,
        reference_range=reference_range,
        reported_flag=reported_flag,
        flag_meaning=flag_meaning,
        range_comparison=comparison,
        source_status=_status(issues),
        issues=issues,
        page_number=page_number,
        source_line=line.strip(),
    )


def _looks_like_test_name(name: str) -> bool:
    lowered = name.lower()
    if len(name.split()) > MAX_NAME_WORDS or not re.search(r"[A-Za-z]{2}", name):
        return False
    return not any(lowered == p or lowered.startswith(p + " ") or lowered.startswith(p + ":") for p in NON_TEST_PREFIXES)


Bounds = tuple[float, float] | tuple[str, float] | None


def _extract_range(rest: str, issues: list[MeasurementIssue]) -> tuple[str | None, Bounds, str]:
    intervals = list(INTERVAL_RE.finditer(rest))
    bound_matches = list(BOUND_RE.finditer(rest)) if not intervals else []
    found = intervals or bound_matches
    if not found:
        return None, None, rest
    if len(found) > 1:
        issues.append("multiple_ranges_found")

    first = found[0]
    reference_range = first.group(0)
    bounds: Bounds
    if intervals:
        bounds = (float(first["lo"]), float(first["hi"]))
    else:
        bounds = (first["op"], float(first["bound"]))

    remainder = rest[: first.start()] + " " + rest[first.end() :]
    remainder = re.sub(r"[()\[\]]", " ", remainder)  # brackets that wrapped the range
    return reference_range, bounds, remainder


def _extract_flag(tokens: list[str]) -> tuple[str | None, FlagMeaning | None, list[str]]:
    for index, token in enumerate(tokens):
        meaning = FLAGS.get(token.strip("()[]*").upper())
        if meaning:
            return token, meaning, tokens[:index] + tokens[index + 1 :]
    return None, None, tokens


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _compare(value: float | None, bounds: Bounds) -> RangeComparison:
    if value is None or bounds is None:
        return "not_compared"
    first, second = bounds
    if isinstance(first, float):
        if value < first:
            return "below_range"
        if value > second:
            return "above_range"
        return "within_range"
    op = first
    if op in ("<", "<=", "≤"):
        exceeded = value >= second if op == "<" else value > second
        return "above_range" if exceeded else "within_range"
    below = value <= second if op == ">" else value < second
    return "below_range" if below else "within_range"


def _status(issues: list[MeasurementIssue]) -> SourceStatus:
    if any(issue in AMBIGUOUS_ISSUES for issue in issues):
        return "ambiguous"
    if issues:
        return "incomplete"
    return "complete"


def _mark_conflicting_duplicates(measurements: list[Measurement]) -> None:
    by_name: dict[str, list[Measurement]] = defaultdict(list)
    for measurement in measurements:
        by_name[measurement.test_name.lower()].append(measurement)
    for group in by_name.values():
        if len({(m.value, m.unit) for m in group}) > 1:
            for measurement in group:
                measurement.issues.append("duplicate_test_conflicting_values")
                measurement.source_status = "ambiguous"
