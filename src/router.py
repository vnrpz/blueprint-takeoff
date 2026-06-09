"""Input-type router (TZ R7 §1).

Classify a PDF project and pick the extraction branch:

    branch 1 vector-table  — schedule table whose text is vector-extractable
    branch 2 raster-table  — schedule table that lives on a raster page
    branch 3 elevations    — no schedule; windows only on elevations/plans
    branch 4 handwritten   — sheet / notes are handwritten

Decision order (most specific first):
    handwritten      -> 4
    schedule + vector text in the schedule -> 1
    schedule + schedule page is raster      -> 2
    no schedule                             -> 3
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List

BRANCH = {1: "vector-table", 2: "raster-table", 3: "elevations", 4: "handwritten"}

# title-block / legend keys -> notation profile
PROFILE_KEYS = {
    "weather_shield": [r"weather\s*shield"],
}

_SCHEDULE_RX = re.compile(r"(window|door)\s+schedule", re.I)


@dataclass
class RouteSignals:
    """Per-document signals (computed from the PDF or supplied in tests)."""
    vector_page_frac: float          # share of pages with extractable vector text
    has_schedule_sheet: bool         # a Window/Door Schedule sheet exists
    schedule_is_vector: bool         # that schedule's table text is extractable
    is_handwritten: bool             # sheet/notes are handwritten
    notation_profile: Optional[str] = None
    schedule_page_index: Optional[int] = None


@dataclass
class Route:
    branch: int
    name: str
    signals: RouteSignals


def classify(s: RouteSignals) -> Route:
    if s.is_handwritten:
        b = 4
    elif s.has_schedule_sheet and s.schedule_is_vector:
        b = 1
    elif s.has_schedule_sheet and not s.schedule_is_vector:
        b = 2
    else:
        b = 3
    return Route(branch=b, name=BRANCH[b], signals=s)


def detect_profile(text: str) -> Optional[str]:
    for prof, pats in PROFILE_KEYS.items():
        if any(re.search(p, text, re.I) for p in pats):
            return prof
    return None


def analyze_pdf(path: str) -> RouteSignals:
    """Compute routing signals from a PDF using PyMuPDF (text only — light).

    A 'schedule sheet' = a page whose text matches 'window/door schedule'.
    schedule_is_vector = that page yields a non-trivial amount of vector text
    (real characters, not just a scanned image with a caption).
    Handwriting is heuristic here (very low text density across pages); the
    pipeline may upgrade with a VLM check when ambiguous.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    n = doc.page_count or 1
    vector_pages = 0
    sched_idx = None
    sched_vector = False
    all_text = []
    char_counts = []
    for i, page in enumerate(doc):
        t = page.get_text("text") or ""
        all_text.append(t)
        char_counts.append(len(t.strip()))
        if len(t.strip()) > 40:
            vector_pages += 1
        if sched_idx is None and _SCHEDULE_RX.search(t):
            sched_idx = i
            # schedule is vector if the schedule page itself carries real text
            sched_vector = len(t.strip()) > 200
    joined = "\n".join(all_text)
    vector_frac = vector_pages / n
    # handwriting heuristic: almost no extractable text anywhere
    is_hand = (vector_frac < 0.15) and (max(char_counts) < 120)
    return RouteSignals(
        vector_page_frac=vector_frac,
        has_schedule_sheet=sched_idx is not None,
        schedule_is_vector=sched_vector,
        is_handwritten=is_hand,
        notation_profile=detect_profile(joined),
        schedule_page_index=sched_idx,
    )


def route_pdf(path: str) -> Route:
    return classify(analyze_pdf(path))
