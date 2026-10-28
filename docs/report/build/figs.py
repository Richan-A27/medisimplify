"""Diagrams for the MediSimplify report (plain academic style to match the Word template)."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
TNR = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
font_manager.fontManager.addfont(TNR)
plt.rcParams["font.family"] = font_manager.FontProperties(fname=TNR).get_name()
EDGE, FILL, ACC = "#222222", "#F2F2F2", "#DCEFEC"


def box(ax, x, y, w, h, title, sub=None, fill=FILL, bold=True, ts=11.5, ss=9.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fill, ec=EDGE, lw=1.1))
    if sub:
        ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", fontsize=ts, weight="bold" if bold else "normal")
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=ss, color="#333333", linespacing=1.15)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=11.5, weight="bold" if bold else "normal")


def arrow(ax, x1, y1, x2, y2, label=None):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.1, color=EDGE, shrinkA=2, shrinkB=2))
    if label:
        ax.text((x1 + x2) / 2 + 0.08, (y1 + y2) / 2, label, fontsize=9, color="#444444", va="center")


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=220)
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.05, facecolor="white")
    plt.close(fig)


# Figure 2.1: synthetic evaluation data
fig, ax = canvas(6.4, 4.6)
steps = [
    ("Fictional report lines", "test name, value, unit, range, flag\nper case category"),
    ("Render PDF (PyMuPDF)", "text layer, scanned (image-only),\npartly scanned or encrypted"),
    ("Gold annotations (cases.json)", "exact values, abnormal basis, ambiguous tests,\nacceptable sources, expected errors"),
    ("Evaluation runner", "extraction · retrieval · validator ·\nsafety language · LLM strategies"),
]
for i, (t, s) in enumerate(steps):
    y = 4.6 - 0.15 - (i + 1) * 1.08
    box(ax, 0.9, y, 4.6, 0.85, t, s, fill=ACC if i == 3 else FILL)
    if i:
        arrow(ax, 3.2, y + 0.85 + 0.23, 3.2, y + 0.87)
save(fig, "fig2_1.png")

# Figure 2.2: PDF preprocessing
fig, ax = canvas(6.4, 6.1)
steps = [
    ("Upload validation", "content type, %PDF- signature, size ≤ 10 MB,\npage limit, password, damaged file"),
    ("Text extraction (PyMuPDF)", "text layer per page in reading order;\nimage-only pages flagged as scanned"),
    ("Row parsing", "one-line rows and column tables;\nmethod column ignored; values copied verbatim"),
    ("Range attachment", "'Bio. Ref. Interval' blocks below a row;\nage/category tables kept as stratified ranges"),
    ("Consistency flags", "missing unit/range, value limits, flag–range\nconflicts, duplicates merged or marked ambiguous"),
    ("Structured report facts", "Measurement records + document warnings\n(no names, dates or free text)"),
]
for i, (t, s) in enumerate(steps):
    y = 6.1 - 0.12 - (i + 1) * 0.98
    box(ax, 0.9, y, 4.6, 0.78, t, s, fill=ACC if i == 5 else FILL)
    if i:
        arrow(ax, 3.2, y + 0.78 + 0.2, 3.2, y + 0.8)
save(fig, "fig2_2.png")

# Figure 3.1: prompt construction, generation and validation
fig, ax = canvas(7.2, 4.9)
inputs = [("System instructions", "11 rules"), ("Report facts", "untrusted data"), ("Few-shot examples", "2 reviewed"), ("Retrieved passages", "MedlinePlus, E1…En")]
for i, (t, s) in enumerate(inputs):
    x = 0.15 + i * 1.78
    box(ax, x, 3.75, 1.6, 0.85, t, s, ts=10, ss=9)
    arrow(ax, x + 0.8, 3.73, 3.6, 3.05)
box(ax, 2.35, 2.25, 2.5, 0.8, "Prompt builder", "content-hashed delimiters,\nprompt version + SHA-256", fill=ACC)
arrow(ax, 3.6, 2.23, 3.6, 1.82)
box(ax, 2.35, 1.0, 2.5, 0.8, "Gemini (JSON schema)", "temperature 0.2, seed 42")
arrow(ax, 4.87, 1.4, 5.35, 1.4)
box(ax, 5.37, 1.0, 1.75, 0.8, "Validator", "values, citations,\nlanguage", fill=ACC)
arrow(ax, 6.25, 0.98, 6.25, 0.55)
ax.text(6.25, 0.38, "passed → shown\nfailed → hidden", ha="center", va="center", fontsize=9.5)
ax.text(0.15, 0.45, "zero-shot: instructions + facts\nfew-shot: + 2 reviewed examples\nRAG: + examples with citations + retrieved passages", fontsize=9.5, va="center", color="#333333")
save(fig, "fig3_1.png")

# Figure 4.1: system architecture
fig, ax = canvas(7.2, 5.4)
box(ax, 0.2, 4.35, 6.8, 0.75, "Next.js web app (browser)", "upload · progress sidebar · results table · references · summary and validation banner")
for x, lab in ((1.2, "POST /api/reports/extract"), (3.6, "POST /api/evidence/retrieve"), (6.0, "POST /api/reports/summarize")):
    arrow(ax, x, 4.33, x, 3.72)
    ax.text(x, 4.03, lab, ha="center", va="center", fontsize=8.5, color="#333333", bbox=dict(fc="white", ec="none", pad=0.6))
box(ax, 0.2, 2.95, 6.8, 0.75, "FastAPI backend", "Pydantic schemas · uniform {code, message} errors · in-memory processing · privacy-safe logs", fill=ACC)
mods = [("PDF service", "PyMuPDF +\nparser"), ("RAG", "MiniLM +\nChromaDB"), ("Prompt builder", "3 strategies"), ("Gemini client", "google-genai"), ("Validator", "rules + language")]
for i, (t, s) in enumerate(mods):
    x = 0.2 + i * 1.38
    box(ax, x, 1.6, 1.24, 0.8, t, s, ts=10, ss=8.5)
    arrow(ax, x + 0.62, 2.93, x + 0.62, 2.42)
box(ax, 1.58, 0.25, 1.24, 0.75, "MedlinePlus", "20 pages,\n226 chunks", ts=10, ss=8.5)
arrow(ax, 2.2, 1.02, 2.2, 1.58)
box(ax, 4.34, 0.25, 1.24, 0.75, "Gemini API", "3.5 Flash-Lite", ts=10, ss=8.5)
arrow(ax, 4.96, 1.58, 4.96, 1.02)
box(ax, 5.72, 0.25, 1.28, 0.75, "Evaluation", "dataset, metrics,\nreplay", ts=10, ss=8.5)
save(fig, "fig4_1.png")
print("ok")
