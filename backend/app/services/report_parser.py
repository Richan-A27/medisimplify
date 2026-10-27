"""Rule-based identification of lab measurements in extracted report text.

The parser is deliberately conservative: it copies text exactly as printed and records issues instead
of guessing. It understands three common layouts:

  one-line rows         Hemoglobin 13.8 g/dL 12.0 - 15.5
  column tables         VITAMIN B-12      E.C.L.I.A      222      pg/mL      197-771
                        (cells separated by 2+ spaces; a method/technology column is ignored)
  ranges below the row  VITAMIN K   LC-MS/MS   0.23   ng/mL
                        Bio. Ref. Interval. :-
                        0.13 - 1.19

A range block with several rows (by age, sex or category) is kept verbatim and marked
`stratified_reference_range`; the parser does not pick a row for the patient. Lines it cannot
interpret are skipped rather than reconstructed.
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
VALUE = rf"(?:[<>]=?|[≤≥])\s?{NUMBER}|{NUMBER}"

LINE_RE = re.compile(
    rf"""^\s*
    (?P<name>[A-Za-z][A-Za-z0-9 ,'()/+\-.]*?)\s*:?\s+
    (?P<value>{VALUE})(?=\s|$)
    (?P<rest>.*)$""",
    re.VERBOSE,
)
VALUE_CELL_RE = re.compile(rf"(?:{VALUE})(?:\s*[HL]{{1,2}}\*?)?")
INTERVAL_RE = re.compile(rf"(?P<lo>{NUMBER})\s*(?:-|–|—|to)\s*(?P<hi>{NUMBER})")
BOUND_RE = re.compile(rf"(?P<op><=|>=|[<>≤≥])\s*(?P<bound>{NUMBER})")
CELL_SPLIT_RE = re.compile(r"\s{2,}")

# A lone range on its own line, optionally followed by a unit: "0.13 - 1.19", "< 5 ng/mL".
LONE_RANGE_RE = re.compile(
    rf"^\s*(?:{NUMBER}\s*(?:-|–|—|to)\s*{NUMBER}|(?:<=|>=|[<>≤≥])\s*{NUMBER})\s*[A-Za-zµ%/0-9^.]*\s*$"
)
RANGE_MARKER_RE = re.compile(
    r"\b(?:bio\.?\s*ref\.?(?:\s*interval)?|biological\s+reference|reference\s+(?:range|interval|value)s?|"
    r"ref\.?\s*(?:range|interval)|normal\s+(?:range|values?))\b\.?\s*[:\-–]*\s*",
    re.IGNORECASE,
)
BLOCK_STOP_RE = re.compile(
    r"^\s*(?:clinical|method|please|interpretation|comments?|notes?|remarks?|tests? done|test name|"
    r"report|disclaimer|page)\b",
    re.IGNORECASE,
)
MAX_LINES_TO_MARKER = 6
MAX_RANGE_LINES = 10

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

# Lines starting with these words describe the patient, the document or a range-table row, not a test.
NON_TEST_PREFIXES = (
    "age", "dob", "date", "time", "patient", "name", "id", "mrn", "phone", "tel", "fax", "page",
    "sex", "gender", "report", "collected", "received", "reported", "printed", "specimen", "accession",
    "lab no", "sample", "ref", "reference", "doctor", "physician", "address", "zip", "room", "bed",
    "above", "below", "under", "over", "upto", "up to", "adult", "adults", "child", "children", "male",
    "female", "men", "women", "deficiency", "deficient", "insufficiency", "insufficient", "sufficiency",
    "sufficient", "toxicity", "toxic", "desirable", "borderline", "optimal", "normal", "low", "high",
)
MAX_NAME_WORDS = 6

AMBIGUOUS_ISSUES: set[MeasurementIssue] = {
    "multiple_ranges_found",
    "flag_conflicts_with_range",
    "duplicate_test_conflicting_values",
    "unrecognized_text",
}

Bounds = tuple[float, float] | tuple[str, float] | None


def parse_measurements(pages: list[PageText]) -> list[Measurement]:
    measurements: list[Measurement] = []
    for page in pages:
        lines = page.text.splitlines()
        index = 0
        while index < len(lines):
            measurement = parse_line(lines[index], page.page_number)
            index += 1
            if measurement is None:
                continue
            if measurement.reference_range is None:
                block, next_index = _range_block_below(lines, index)
                if block:
                    measurement = _attach_range_block(measurement, block)
                    index = next_index
            measurements.append(measurement)
    measurements = _merge_identical_duplicates(measurements)
    _mark_conflicting_duplicates(measurements)
    return measurements


def parse_line(line: str, page_number: int) -> Measurement | None:
    parts = _split_columns(line) or _split_regex(line)
    if parts is None:
        return None
    name, value_text, rest = parts
    if not _looks_like_test_name(name):
        return None

    issues: list[MeasurementIssue] = []
    reference_range, bounds, rest = _extract_range(rest, issues)
    reported_flag, flag_meaning, remaining = _extract_flag(rest.split())

    unit = remaining[0] if remaining else None
    if unit is not None and not re.search(r"[A-Za-z%µ]", unit):
        return None  # e.g. a postcode "122 015", not a value with a unit
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
    _check_flag_conflict(flag_meaning, comparison, issues)

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


def _split_columns(line: str) -> tuple[str, str, str] | None:
    """Column layout: name | [method...] | value | unit | [range]. Method cells contain no digits."""
    cells = [cell for cell in CELL_SPLIT_RE.split(line.strip()) if cell]
    if len(cells) < 3:
        return None
    for position in range(1, len(cells)):
        if VALUE_CELL_RE.fullmatch(cells[position]):
            break
    else:
        return None
    if any(re.search(r"\d", cell) for cell in cells[1:position]):
        return None
    value_cell = cells[position].split()
    value_text = value_cell[0].replace(" ", "")
    if value_text in ("<", ">", "<=", ">=", "≤", "≥") and len(value_cell) > 1:
        value_text += value_cell[1]
        value_cell = value_cell[1:]
    flag_tail = value_cell[1:]  # "10.2 H" in one cell
    name = " ".join(cells[0].split()).rstrip(" :,-")
    rest = " ".join(flag_tail + cells[position + 1 :])
    return name, value_text, rest


def _split_regex(line: str) -> tuple[str, str, str] | None:
    match = LINE_RE.match(line)
    if not match:
        return None
    name = " ".join(match["name"].split()).rstrip(" :,-")
    return name, match["value"].replace(" ", ""), match["rest"].strip()


def _looks_like_test_name(name: str) -> bool:
    lowered = name.lower()
    if len(name.split()) > MAX_NAME_WORDS or not re.search(r"[A-Za-z]{2}", name):
        return False
    if name.count("(") != name.count(")") or not re.search(r"[A-Za-z0-9)]$", name):
        return False
    return not any(
        lowered == p or lowered.startswith(p + " ") or lowered.startswith(p + ":") for p in NON_TEST_PREFIXES
    )


def _range_block_below(lines: list[str], start: int) -> tuple[list[str], int]:
    """Find a 'Bio. Ref. Interval' style block shortly after a result row. Returns (range lines, next index)."""
    marker_index = None
    seen = 0
    for index in range(start, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        seen += 1
        if seen > MAX_LINES_TO_MARKER or BLOCK_STOP_RE.match(line):
            return [], start
        if RANGE_MARKER_RE.search(line):
            marker_index = index
            break
        if parse_line(line, 0) is not None:
            return [], start  # the next result row came first
    if marker_index is None:
        return [], start

    block: list[str] = []
    tail = RANGE_MARKER_RE.split(lines[marker_index], maxsplit=1)[-1].strip(" :-–")
    if re.search(r"\d", tail) and (INTERVAL_RE.search(tail) or BOUND_RE.search(tail)):
        block.append(" ".join(tail.split()))

    index = marker_index + 1
    while index < len(lines) and len(block) < MAX_RANGE_LINES:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if BLOCK_STOP_RE.match(line):
            break
        if not re.search(r"\d", line):
            if block:
                break
            index += 1  # a header such as "Age   Reference range"
            continue
        if not (INTERVAL_RE.search(line) or BOUND_RE.search(line)) or parse_line(line, 0) is not None:
            break  # not a range line, or the next result row
        block.append(" ".join(line.split()))
        index += 1
    return block, (index if block else start)


def _attach_range_block(measurement: Measurement, block: list[str]) -> Measurement:
    issues = [i for i in measurement.issues if i != "missing_reference_range"]
    source_line = "\n".join([measurement.source_line, *block])
    if len(block) == 1 and LONE_RANGE_RE.match(block[0]):
        range_issues: list[MeasurementIssue] = []
        reference_range, bounds, _ = _extract_range(block[0], range_issues)
        comparison = _compare(measurement.value_numeric, bounds)
        issues += range_issues
        _check_flag_conflict(measurement.flag_meaning, comparison, issues)
    else:
        reference_range = "; ".join(block)
        comparison = "not_compared"
        issues.append("stratified_reference_range")
    return measurement.model_copy(
        update={
            "reference_range": reference_range,
            "range_comparison": comparison,
            "issues": issues,
            "source_status": _status(issues),
            "source_line": source_line,
        }
    )


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


def _check_flag_conflict(meaning: FlagMeaning | None, comparison: RangeComparison, issues: list[MeasurementIssue]) -> None:
    if (meaning == "high" and comparison == "below_range") or (meaning == "low" and comparison == "above_range"):
        issues.append("flag_conflicts_with_range")


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


def _range_quality(m: Measurement) -> int:
    if m.reference_range is None:
        return 0
    return 1 if "stratified_reference_range" in m.issues else 2


def _merge_identical_duplicates(measurements: list[Measurement]) -> list[Measurement]:
    """A summary page often repeats a detailed result. Keep one copy, preferring a simple printed range."""
    best: dict[tuple[str, str, str | None], Measurement] = {}
    order: list[tuple[str, str, str | None]] = []
    for m in measurements:
        key = (m.test_name.lower(), m.value, m.unit)
        if key not in best:
            best[key] = m
            order.append(key)
        elif _range_quality(m) > _range_quality(best[key]):
            best[key] = m
    return [best[key] for key in order]


def _mark_conflicting_duplicates(measurements: list[Measurement]) -> None:
    by_name: dict[str, list[Measurement]] = defaultdict(list)
    for measurement in measurements:
        by_name[measurement.test_name.lower()].append(measurement)
    for group in by_name.values():
        if len({(m.value, m.unit) for m in group}) > 1:
            for measurement in group:
                measurement.issues.append("duplicate_test_conflicting_values")
                measurement.source_status = "ambiguous"
