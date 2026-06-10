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


_UNIT_TABLE_RX = re.compile(r"rough\s+opening", re.I)


def _has_unit_table(text: str) -> bool:
    up = text.upper()
    if _SCHEDULE_RX.search(text):
        return True
    return ("ROUGH OPENING" in up) and (("UNIT" in up) or ("MARK" in up) or "WINDOW" in up or "DOOR" in up)


def _vlm_classify_raster(path: str, page_index: int, provider_spec: str = "anthropic:claude-opus-4-8") -> str:
    try:
        from src.pdf_utils import rasterize
        from src import vlm
        pgs = rasterize(path, "/tmp/router_cls", dpi=200, pages=[page_index])
        prompt = ("Look at this single construction-drawing page. Answer with EXACTLY one token: "
                  "TABLE if a printed WINDOW/DOOR SCHEDULE TABLE is present (grid of rows with marks/sizes/qty); "
                  "HANDWRITTEN if the page is predominantly handwritten notes or a hand sketch; "
                  "PLAN otherwise. One token only.")
        r = vlm.get_provider(provider_spec).extract(str(pgs[0].image_path), prompt)
        return (r.raw_text or "").strip().upper().split()[0] if (r.raw_text or "").strip() else "PLAN"
    except Exception:
        return "PLAN"


def analyze_pdf(path: str, *, vlm_for_raster: bool = True) -> RouteSignals:
    """Compute routing signals. Detects vector unit/schedule tables (incl. order
    forms with a Rough-Opening column), and for near-text-free raster docs uses a
    VLM to tell a printed schedule table (raster-table) from handwriting."""
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
        if sched_idx is None and _has_unit_table(t) and len(t.strip()) > 200:
            sched_idx = i
            sched_vector = True
    joined = "\n".join(all_text)
    vector_frac = vector_pages / n
    is_hand = False
    if sched_idx is None and vector_frac < 0.15 and max(char_counts) < 120:
        if vlm_for_raster:
            # Vote over a few sampled pages: a printed schedule TABLE or
            # predominantly HANDWRITTEN content anywhere routes the doc.
            sample = sorted(set([0, n // 2, n - 1]))[:3]
            table_pg = None
            hand_votes = 0
            for pi in sample:
                v = _vlm_classify_raster(path, pi)
                if v.startswith("TABLE") and table_pg is None:
                    table_pg = pi
                elif v.startswith("HAND"):
                    hand_votes += 1
            if table_pg is not None:
                sched_idx = table_pg
                sched_vector = False
            elif hand_votes > 0:
                is_hand = True
        else:
            is_hand = max(char_counts) < 120
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
