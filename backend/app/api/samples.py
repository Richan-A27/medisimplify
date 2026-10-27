"""Synthetic sample reports for demos, so nobody needs a real report to try the app."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from scripts.synthetic_reports import all_samples

router = APIRouter(prefix="/samples", tags=["samples"])

# Order and wording shown in the UI. Every sample is fictional.
SAMPLE_INFO: dict[str, tuple[str, str]] = {
    "metabolic_abnormal": ("Metabolic panel (abnormal)", "Flagged and unflagged values outside the printed ranges."),
    "cbc_normal": ("Blood count (in range)", "All values inside the printed ranges."),
    "columnar_lab": ("Column layout (ranges below rows)", "Lab-style table with a method column and age-based ranges."),
    "missing_ranges": ("Missing ranges", "Rows without a reference range or unit, and a value given as a limit."),
    "conflicting_values": ("Conflicting values", "A test reported twice and a flag that contradicts its range."),
    "prompt_injection": ("Hidden instructions", "Comment lines that try to instruct the AI; treated as data."),
    "no_results": ("No test results", "A clinical note with nothing to summarise."),
    "scanned_image_only": ("Scanned PDF", "Image-only PDF; text extraction should fail clearly."),
    "partially_scanned": ("Partly scanned PDF", "One text page and one image-only page."),
}


class SampleInfo(BaseModel):
    id: str
    title: str
    description: str


@router.get("", response_model=list[SampleInfo])
def list_samples() -> list[SampleInfo]:
    return [SampleInfo(id=key, title=title, description=desc) for key, (title, desc) in SAMPLE_INFO.items()]


@router.get("/{sample_id}", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def get_sample(sample_id: str) -> Response:
    if sample_id not in SAMPLE_INFO:
        raise HTTPException(status_code=404, detail="Unknown sample.")
    data = all_samples()[sample_id]
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="synthetic-{sample_id}.pdf"'},
    )
