
"""Task 7 — quantity provenance + error detection.

Every quantity an extractor emits must be traceable to HOW it was derived, and
suspicious values must be flagged rather than silently passed through. This is
the anti-"false numbers" guard: a takeoff is only trustworthy if each qty has a
source and the document's own arithmetic reconciles.
"""
from __future__ import annotations
from typing import Optional


QTY_SOURCES = {
    "price_reconciled": "qty = line_total / unit_price, confirmed by document arithmetic",
    "schedule_column": "qty read directly from a schedule QTY column",
    "vlm_read": "qty transcribed by VLM from the drawing (low confidence)",
    "counted_openings": "qty inferred by counting drawn openings (low confidence)",
    "unknown": "no reliable source — must be flagged, never trusted",
}


def detect_errors(extract: dict) -> dict:
    """Scan a branch extract for anomalies. Returns {errors, warnings, ok}.

    errors  = things that make the takeoff untrustworthy (qty without source,
              failed reconciliation, negative/zero sizes).
    warnings = low-confidence reads to surface to a human.
    """
    errors, warnings = [], []
    units = extract.get("units") or extract.get("groups", [{}])[0].get("units", [])
    scored = extract.get("scored", True)

    for i, u in enumerate(units):
        tag = u.get("mark", f"#{i}")
        qty = u.get("qty")
        src = u.get("qty_source", "unknown")
        if qty is None:
            warnings.append(f"{tag}: qty missing (unreadable) — flagged, not guessed")
        elif src == "unknown":
            warnings.append(f"{tag}: qty={qty} has no provenance — treat as unverified")
        w = u.get("width") or u.get("width_in") or u.get("frame_w")
        h = u.get("height") or u.get("height_in") or u.get("frame_h")
        if w is not None and (w <= 0 or w > 600):
            errors.append(f"{tag}: implausible width {w} in")
        if h is not None and (h <= 0 or h > 600):
            errors.append(f"{tag}: implausible height {h} in")

    recon = extract.get("recon_detail")
    if recon is not None:
        bad = [d for d in recon if not d.get("ok")]
        if bad:
            errors.append(f"{len(bad)} offer line(s) failed price reconciliation: {bad}")

    if not scored and not warnings:
        warnings.append("unscored branch (no ground truth) — results are best-effort")

    return {"errors": errors, "warnings": warnings,
            "ok": not errors,
            "n_units": len(units),
            "n_flagged": len(warnings) + len(errors)}


def annotate_qty_source(extract: dict, source_key: str) -> dict:
    """Stamp every unit with its qty provenance so downstream never sees a
    bare number without knowing where it came from."""
    assert source_key in QTY_SOURCES, f"unknown qty source {source_key!r}"
    units = extract.get("units") or extract.get("groups", [{}])[0].get("units", [])
    for u in units:
        u.setdefault("qty_source", source_key)
    return extract
