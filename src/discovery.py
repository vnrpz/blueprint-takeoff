"""Discovery layer (R6): transform extracted units → offer form.

R6 update: per-view shim constants (windows vs doors).

Per TZ §19 R4 #4:
* Input: extracted units with drawing-faithful marks, RO/nominal sizes, qty.
* Output: units in offer form (frame size = RO - shim, folded mirror pairs,
  tempered/egress flags per IRC).

Mappings:
* RO → frame: subtract per-view shim. Windows use 0.75 total on each dim;
  doors use 0.75 total on width but only 0.5 on height (threshold has no
  allowance under the unit). Per-unit override via panel.rough_opening +
  shim_per_side_in argument (kept for backward compatibility).
* Mirror pairs fold via existing spec_group_key (kind, role, w, h).
* IRC R308.4: glass tempered when adjacent to door or sill < 18 in.
* IRC R310: egress required for bedrooms; clear opening >= 5.7 sqft.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from src.schema import Unit, Panel, RoughOpening


# Legacy symmetric shim (per side). Still exported so older call sites that
# pass `shim_per_side_in=` directly keep working.
DEFAULT_SHIM_PER_SIDE_IN = 0.375


# R6 per-view shim, expressed as TOTAL reduction on each dim (both sides
# combined). Lookup keyed by Unit.kind.
#  windows: 0.75 w / 0.75 h  -> 0.375 per side, both dims
#  doors:   0.75 w / 0.5 h   -> 0.375 per side on width; 0.25 per side on
#                              height (effectively all allowance on the
#                              head -- threshold sits on subfloor with no
#                              shim).
PER_VIEW_TOTAL_SHIM_IN = {
    "window": {"w": 0.75, "h": 0.75},
    "door":   {"w": 0.75, "h": 0.5},
}


def ro_to_frame(ro_w: float, ro_h: float, *,
                kind: str = "window",
                shim_per_side_in: Optional[float] = None,
                ) -> Tuple[float, float]:
    """RO -> frame.

    Args:
      ro_w, ro_h: rough opening width / height (inches).
      kind: "window" or "door" -- selects the per-view total shim. Ignored
            when `shim_per_side_in` is given.
      shim_per_side_in: legacy override. When provided, applies symmetric
            2*x reduction on both dims (R4/R5 behaviour).
    """
    if shim_per_side_in is not None:
        return (ro_w - 2 * shim_per_side_in, ro_h - 2 * shim_per_side_in)
    s = PER_VIEW_TOTAL_SHIM_IN.get(kind, PER_VIEW_TOTAL_SHIM_IN["window"])
    return (ro_w - s["w"], ro_h - s["h"])


def transform_unit(u: Unit, *,
                   shim_per_side_in: Optional[float] = None,
                   ) -> Unit:
    """Return a new Unit with frame-size panels derived from RO (if present).

    Per-view shim is selected from `u.kind` ("window"/"door"). Pass
    `shim_per_side_in=` to force legacy symmetric behaviour.

    If a unit has no rough_opening attached, leave its panel sizes unchanged
    -- the assumption is the extractor already reported frame size."""
    new_panels = list(u.panels)
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
        fw, fh = ro_to_frame(
            u.rough_opening.w_in, u.rough_opening.h_in,
            kind=u.kind, shim_per_side_in=shim_per_side_in,
        )
        p0 = new_panels[0]
        new_panels[0] = Panel(
            role=p0.role, width_in=fw, height_in=fh,
            glass=p0.glass, u_factor=p0.u_factor, egress=p0.egress,
            clear_opening_sqft=p0.clear_opening_sqft,
        )
    return out


def transform_all(units: Iterable[Unit], *,
                  shim_per_side_in: Optional[float] = None,
                  ) -> List[Unit]:
    return [transform_unit(u, shim_per_side_in=shim_per_side_in) for u in units]
