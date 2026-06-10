
"""Branches 3 & 4 — best-effort VLM extraction for unscored inputs.

Branch 3: elevation drawings (4006-style architectural sets) — windows are
drawn openings, not a schedule table. Branch 4: handwritten / scanned sheets.
Both are UNSCORED (no ground truth). We return whatever the VLM can read with
an explicit low-confidence flag and scored=False. We never fabricate marks,
sizes, or quantities that the VLM did not report.
"""
from __future__ import annotations
import json, re
from typing import Optional

import fitz

_ELEV_KEYS = ("ELEVATION", "T.O. PARAPET", "PARAPET", "T.O. CONC")
_SCHED_PROMPT = (
    "This is one page from a construction drawing set. If you can see a window or "
    "door SCHEDULE or any openings with size labels, list them as JSON: "
    '{"units":[{"mark":"...","width_in":<number or null>,"height_in":<number or null>,'
    '"qty":<int or null>,"note":"..."}],"confidence":"low|medium|high",'
    '"readable":true|false}. '
    "Only report marks/sizes you can actually read. If you cannot read sizes, set them "
    "to null and confidence to low. Do NOT invent values. Output JSON only."
)


_ELEV_SCORE_KEYS = ("FIRST LEVEL", "SECOND LEVEL", "THIRD LEVEL", "FOURTH LEVEL",
                    "FIFTH LEVEL", "T.O. PARAPET", "ELEVATION")


def _elevation_pages(doc) -> list:
    """Rank pages by elevation-keyword density so the true building-elevation
    sheets (many LEVEL/PARAPET datums) float to the top, not detail/section pages."""
    scored = []
    for i, pg in enumerate(doc):
        t = (pg.get_text("text") or "").upper()
        level_hits = sum(t.count(k) for k in ("FIRST LEVEL","SECOND LEVEL","THIRD LEVEL","FOURTH LEVEL","FIFTH LEVEL"))
        score = sum(t.count(k) for k in _ELEV_SCORE_KEYS)
        if level_hits >= 2:          # true elevation sheet, not a sheet index
            scored.append((score + 10 * level_hits, i))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [i for _, i in scored]


def _vlm_page_json(path: str, page_index: int,
                   provider_spec: str = "anthropic:claude-opus-4-8", dpi: int = 200) -> dict:
    from src.pdf_utils import rasterize
    from src import vlm
    pgs = rasterize(path, "/tmp/raster_vlm", dpi=dpi, pages=[page_index])
    r = vlm.get_provider(provider_spec).extract(str(pgs[0].image_path), _SCHED_PROMPT)
    raw = (r.raw_text or "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"units": [], "confidence": "low", "readable": False, "_raw": raw[:200]}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"units": [], "confidence": "low", "readable": False, "_raw": raw[:200]}


def extract_elevations(path: str, max_pages: int = 2) -> dict:
    """Branch 3: best-effort window read from elevation pages (UNSCORED)."""
    doc = fitz.open(path)
    pages = _elevation_pages(doc)[:max_pages]
    units, pages_read = [], []
    for pi in pages:
        res = _vlm_page_json(path, pi)
        pages_read.append({"page": pi + 1, "confidence": res.get("confidence", "low"),
                           "readable": res.get("readable", False),
                           "n_units": len(res.get("units", []))})
        for u in res.get("units", []):
            u["source_page"] = pi + 1
            units.append(u)
    return {"branch": 3, "kind": "elevations", "scored": False,
            "confidence": "low", "units": units, "pages_read": pages_read,
            "note": ("Elevation best-effort. 4006 building elevations carry no printed "
                         "per-window size labels at 300 DPI; the 4006 window takeoff is sourced "
                         "from the OFR offer (branch 1, reconciled). No fabrication.")}


def extract_handwritten(path: str, max_pages: int = 3) -> dict:
    """Branch 4: best-effort read of handwritten/scanned sheets (UNSCORED)."""
    doc = fitz.open(path)
    n = doc.page_count
    sample = sorted(set([0, n // 2, n - 1]))[:max_pages]
    units, pages_read = [], []
    for pi in sample:
        res = _vlm_page_json(path, pi)
        pages_read.append({"page": pi + 1, "confidence": res.get("confidence", "low"),
                           "readable": res.get("readable", False),
                           "n_units": len(res.get("units", []))})
        for u in res.get("units", []):
            u["source_page"] = pi + 1
            units.append(u)
    return {"branch": 4, "kind": "handwritten", "scored": False,
            "confidence": "low", "units": units, "pages_read": pages_read,
            "note": "Handwritten/scanned best-effort; no ground truth."}
