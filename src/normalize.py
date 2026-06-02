"""Normalization (TZ §5).

* Parse fractional inches: '72 1/2' -> 72.5, '36 3/16' -> 36.1875.
* Round dimensions for spec-group key (default 0.5in bucket).
* U-factor bucket: 0.01.
* Mirror-pair folding: left/right hand removed from key.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple, Iterable, List, Dict

from src.schema import Unit, Panel

_FRACTION = re.compile(
    r"""
    ^\s*
    (?:(?P<whole>\d+)\s+)?            # optional whole part
    (?:(?P<num>\d+)\s*/\s*(?P<den>\d+))?  # optional fraction
    \s*$
    """,
    re.VERBOSE,
)
_DECIMAL = re.compile(r"^\s*(?P<v>-?\d+(?:\.\d+)?)\s*$")


def parse_inches(s: str | float | int) -> float:
    """Parse a measurement to decimal inches.

    Accepts:
        '72'        -> 72.0
        '72 1/2'    -> 72.5
        '36 3/16'   -> 36.1875
        '1/2'       -> 0.5
        72.5        -> 72.5
        '72.5'      -> 72.5

    Raises ValueError on unparseable input.
    """
    if isinstance(s, (int, float)):
        return float(s)
    if not isinstance(s, str):
        raise ValueError(f"parse_inches: cannot parse {type(s).__name__}")
    raw = s.strip().replace('"', "").replace("''", "").replace("”", "")
    if not raw:
        raise ValueError("parse_inches: empty string")
    md = _DECIMAL.match(raw)
    if md:
        return float(md.group("v"))
    mf = _FRACTION.match(raw)
    if mf and (mf.group("whole") or mf.group("num")):
        whole = int(mf.group("whole") or 0)
        num = mf.group("num")
        den = mf.group("den")
        if num and den:
            return whole + int(num) / int(den)
        return float(whole)
    raise ValueError(f"parse_inches: unparseable {s!r}")


def round_dim(v: float, bucket: float = 0.5) -> float:
    return round(v / bucket) * bucket


def ufactor_bucket(u: Optional[float], step: float = 0.01) -> Optional[str]:
    if u is None:
        return None
    return f"{round(u / step) * step:.2f}"


@dataclass(frozen=True)
class SpecGroupKey:
    """Hashable key for matching predicted vs GT groups."""
    kind: str
    panels: Tuple[Tuple[str, float, float, Optional[str], Optional[str], Optional[bool]], ...]

    def __str__(self) -> str:  # for human-readable error messages
        return f"{self.kind}|{self.panels}"


def spec_group_key(u: Unit, *, bucket: float = 0.5) -> SpecGroupKey:
    """Build the matching key per TZ §5.

    For composite units we sort panels by (role, w, h) so [door, window]
    and [window, door] orderings collapse to the same key. This is the
    'mirror / hand folding' described in the brief.
    """
    panels = []
    for p in u.panels:
        panels.append((
            p.role,
            round_dim(p.width_in, bucket),
            round_dim(p.height_in, bucket),
            p.glass,
            ufactor_bucket(p.u_factor),
            p.egress,
        ))
    panels.sort()
    return SpecGroupKey(kind=u.kind, panels=tuple(panels))


def group_units(units: Iterable[Unit], *, bucket: float = 0.5) -> Dict[SpecGroupKey, int]:
    """Aggregate units → {spec_group_key: total_qty}. Mirror pairs fold here."""
    agg: Dict[SpecGroupKey, int] = {}
    for u in units:
        k = spec_group_key(u, bucket=bucket)
        agg[k] = agg.get(k, 0) + int(u.qty)
    return agg
