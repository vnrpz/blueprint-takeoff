"""Output schema (TZ §4). One dataclass shape for every pipeline.

A Unit is a single spec-group entry. For composite assemblies (window+door
coupled, corner90, etc.) panels[] has multiple entries but qty is the unit
count, not the panel count.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Literal, Optional, Tuple, Dict, Any

Kind = Literal["window", "door", "composite"]
Glass = Literal["tempered", "annealed", "mixed"]
Region = Literal["schedule", "elevation", "plan", "notes", "section"]


@dataclass
class Panel:
    role: Literal["window", "door"]
    width_in: float
    height_in: float
    glass: Optional[Glass] = None
    u_factor: Optional[float] = None
    egress: Optional[bool] = None
    clear_opening_sqft: Optional[float] = None


@dataclass
class Evidence:
    page: int
    region: Region
    bbox: Tuple[float, float, float, float]  # x, y, w, h in page coords


@dataclass
class RoughOpening:
    w_in: float
    h_in: float


@dataclass
class Unit:
    unit_id: str
    kind: Kind
    panels: List[Panel]
    qty: int
    source_marks: List[str] = field(default_factory=list)
    color_interior: Optional[str] = None
    color_exterior: Optional[str] = None
    rough_opening: Optional[RoughOpening] = None
    evidence: List[Evidence] = field(default_factory=list)
    confidence: float = 1.0
    flags: List[str] = field(default_factory=list)
    discovery_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Unit":
        panels = [Panel(**p) for p in d.get("panels", [])]
        evidence = [Evidence(**e) for e in d.get("evidence", [])]
        ro = d.get("rough_opening")
        rough_opening = RoughOpening(**ro) if ro else None
        return Unit(
            unit_id=d["unit_id"],
            kind=d["kind"],
            panels=panels,
            qty=int(d["qty"]),
            source_marks=list(d.get("source_marks", [])),
            color_interior=d.get("color_interior"),
            color_exterior=d.get("color_exterior"),
            rough_opening=rough_opening,
            evidence=evidence,
            confidence=float(d.get("confidence", 1.0)),
            flags=list(d.get("flags", [])),
            discovery_gaps=list(d.get("discovery_gaps", [])),
        )
