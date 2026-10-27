"""Write synthetic sample PDFs for manual testing in the UI.

Usage (from backend/):  .venv/bin/python -m scripts.generate_sample_pdfs [output_dir]
Default output: ../samples/
"""

import sys
from pathlib import Path

from scripts.synthetic_reports import all_samples

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "samples"


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for name, data in all_samples().items():
        path = output / f"{name}.pdf"
        path.write_bytes(data)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
