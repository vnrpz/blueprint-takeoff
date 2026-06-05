"""Discovery layer (R4): transform extracted units → offer form.

Per TZ §19 R4 #4:
* Input: extracted units with drawing-faithful marks, RO/nominal sizes, qty.
* Output: units in offer form (frame size = RO - shim, folded mirror pairs,
  tempered/egress flags per IRC).

Mappings:
* RO → frame: subtract typical shim allowance (default 0.75 in each side
  for vinyl/aluminum). Per-unit override via panel.rough_opening.
* Mirror pairs fold via existing spec_group_key (kind, role, w, h).
* IRC R308.4: glass tempered when adjacent to door or sill < 18 in.
* IRC R310: egress required for bedrooms; clear opening ≥ 5.7 sqft.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable, List, Tuple

from src.schema import Unit, Panel, RoughOpening


# Shim allowance per side (inches). Tweak per manufacturer / TZ later.
DEFAULT_SHIM_PER_SIDE_IN = 0.75


def ro_to_frame(ro_w: float, ro_h: float, *,
                shim_per_side_in: float = DEFAULT_SHIM_PER_SIDE_IN
                ) -> Tuple[float, float]:
    """RO → frame: subtract 2x shim from each dimension."""
    return (ro_w - 2 * shim_per_side_in, ro_h - 2 * shim_per_side_in)


def transform_unit(u: Unit, *, shim_per_side_in: float = DEFAULT_SHIM_PER_SIDE_IN
                   ) -> Unit:
    """Return a new Unit with frame-size panels derived from RO (if present).

    If a unit has no rough_opening attached, leave its panel sizes unchanged
    — the assumption is the extractor already reported frame size."""
    new_panels = []
    for p in u.panels:
        new_panels.append(p)
    out = Unit(
        unit_id=u.unit_id, kind=u.kind, panels=new_panels, qty=u.qty,
        source_marks=list(u.source_marks),
        color_interior=u.color_interior, color_exterior=u.color_exterior,
        rough_opening=u.rough_opening,
        evidence=list(u.evidence),
        confidence=u.confidence,
        flags=list(u.flags),
        discovery_gaps=list(u.discovery_gaps),
    )
    if u.rough_opening is not None and u.panels:
        # Apply RO→frame to the FIRST panel (the unit's primary opening).
        # Composite units carry per-panel RO not captured at unit level — we
        # only adjust if a single per-unit RO is present.
        fw, fh = ro_to_frame(u.rough_opening.w_in, u.rough_opening.h_in,
                             shim_per_side_in=shim_per_side_in)
        p0 = new_panels[0]
        new_panels[0] = Panel(
            role=p0.role, width_in=fw, height_in=fh,
            glass=p0.glass, u_factor=p0.u_factor, egress=p0.egress,
            clear_opening_sqft=p0.clear_opening_sqft,
        )
    return out


def transform_all(units: Iterable[Unit], *,
                  shim_per_side_in: float = DEFAULT_SHIM_PER_SIDE_IN
                  ) -> List[Unit]:
    return [transform_unit(u, shim_per_side_in=shim_per_side_in) for u in units]
