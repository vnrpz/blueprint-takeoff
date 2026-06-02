"""Robust parse model JSON into List[Unit]. Tolerant of common deviations."""
from __future__ import annotations

from typing import Any, List

from src.schema import Unit, Panel, Evidence, RoughOpening
from src.normalize import parse_inches


def _to_float(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return parse_inches(v)
    raise ValueError(f"cannot coerce {v!r} to float")


def _coerce_panel(d: dict) -> Panel:
    return Panel(
        role=d.get("role", "window"),
        width_in=_to_float(d["width_in"]),
        height_in=_to_float(d["height_in"]),
        glass=d.get("glass"),
        u_factor=(float(d["u_factor"]) if d.get("u_factor") is not None else None),
        egress=(bool(d["egress"]) if d.get("egress") is not None else None),
        clear_opening_sqft=(float(d["clear_opening_sqft"]) if d.get("clear_opening_sqft") is not None else None),
    )


def parse_units(items: Any) -> List[Unit]:
    if items is None:
        return []
    if isinstance(items, dict):
        # tolerate {"units": [...]}
        items = items.get("units") or items.get("data") or [items]
    if not isinstance(items, list):
        return []
    out: List[Unit] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            continue
        try:
            panels = [_coerce_panel(p) for p in raw.get("panels", [])]
            if not panels:
                continue
            ro_raw = raw.get("rough_opening")
            ro = RoughOpening(w_in=_to_float(ro_raw["w_in"]), h_in=_to_float(ro_raw["h_in"])) if ro_raw else None
            ev = [Evidence(page=int(e.get("page", 0)),
                           region=e.get("region", "elevation"),
                           bbox=tuple(e.get("bbox", (0, 0, 0, 0)))) for e in raw.get("evidence", []) if isinstance(e, dict)]
            out.append(Unit(
                unit_id=str(raw.get("unit_id") or f"G{i+1}"),
                kind=raw.get("kind", "window"),
                panels=panels,
                qty=int(raw.get("qty", 1)),
                source_marks=list(raw.get("source_marks", [])),
                color_interior=raw.get("color_interior"),
                color_exterior=raw.get("color_exterior"),
                rough_opening=ro,
                evidence=ev,
                confidence=float(raw.get("confidence", 0.7)),
                flags=list(raw.get("flags", [])),
                discovery_gaps=list(raw.get("discovery_gaps", [])),
            ))
        except Exception:  # tolerate one bad row, continue
            continue
    return out
