"""Dimension-notation decoder (TZ R7 §2) — deterministic, in code, never VLM.

The model only reads the raw string from a schedule cell; this module turns
that string into width/height inches. Profile is chosen by the router from the
sheet's title block / legend. Unknown profile -> flag, never a silent guess.

Weather Shield profile (sheet 745):
    4-digit "WXYZ" = W'X" wide x Y'Z" high
        2870 -> 2'8" x 7'0" -> 32 x 84
        3050 -> 3'0" x 5'0" -> 36 x 60
        2856 -> 2'8" x 5'6" -> 32 x 66
        3180 -> 3'1" x 8'0" -> 37 x 96   (door D)
    composite "N-WXYZ" = N units mulled at the same height
        2-2870 -> 64 x 84   3-2870 -> 96 x 84
    explicit literal  2'-8" x 7'-0"  /  32 x 84  /  fractional inches ok
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from src.normalize import parse_inches


class NotationError(ValueError):
    """Raised when a string cannot be decoded under the active profile."""


@dataclass(frozen=True)
class Decoded:
    width_in: float
    height_in: float
    mull_count: int = 1          # N for composite N-XXYY (single-unit width * N)
    unit_width_in: Optional[float] = None  # per-mull width before *N


def _ft_in_pair(d2: str) -> float:
    """'28' -> 2'8" -> 32.0 inches.  Two digits: feet, inches."""
    if len(d2) != 2 or not d2.isdigit():
        raise NotationError(f"weather_shield: pair {d2!r} is not 2 digits")
    feet = int(d2[0])
    inch = int(d2[1])
    return feet * 12 + inch


def decode_weather_shield(code: str) -> Decoded:
    """Decode a Weather Shield size code (4-digit or N-prefixed composite)."""
    s = str(code).strip().upper()
    m = re.match(r"^(?:(\d+)\s*-\s*)?(\d{4})$", s)
    if not m:
        raise NotationError(f"weather_shield: {code!r} is not a 4-digit code")
    n = int(m.group(1)) if m.group(1) else 1
    quad = m.group(2)
    w_unit = _ft_in_pair(quad[:2])
    h = _ft_in_pair(quad[2:])
    return Decoded(width_in=w_unit * n, height_in=h, mull_count=n, unit_width_in=w_unit)


_LITERAL = re.compile(
    r"""^\s*
    (?P<wf>\d+)\s*'\s*[- ]?\s*(?P<wi>\d+(?:\s+\d+/\d+)?)\s*"?\s*
    [xX×]\s*
    (?P<hf>\d+)\s*'\s*[- ]?\s*(?P<hi>\d+(?:\s+\d+/\d+)?)\s*"?\s*$""",
    re.VERBOSE,
)
_INCHES = re.compile(r"""^\s*(?P<w>[\d /.]+?)\s*[xX×]\s*(?P<h>[\d /.]+?)\s*$""")


def decode_literal(s: str) -> Decoded:
    """Decode explicit literals:  2'-8" x 7'-0"  or  32 x 84  (fractional ok)."""
    txt = str(s).strip()
    m = _LITERAL.match(txt)
    if m:
        w = int(m.group("wf")) * 12 + parse_inches(m.group("wi"))
        h = int(m.group("hf")) * 12 + parse_inches(m.group("hi"))
        return Decoded(width_in=w, height_in=h)
    m = _INCHES.match(txt)
    if m:
        return Decoded(width_in=parse_inches(m.group("w")), height_in=parse_inches(m.group("h")))
    raise NotationError(f"literal: cannot parse {s!r}")


_PROFILES = {
    "weather_shield": decode_weather_shield,
}


def decode(code: str, profile: str) -> Decoded:
    """Decode `code` under the named profile. Falls back to explicit literals.

    Unknown profile -> NotationError (flag upstream, do not silently guess).
    """
    txt = str(code).strip()
    # explicit literal always wins (it carries its own units)
    if re.search(r"['\"]", txt) or re.match(r"^\s*[\d /.]+\s*[xX×]\s*[\d /.]+\s*$", txt):
        try:
            return decode_literal(txt)
        except NotationError:
            pass
    fn = _PROFILES.get(profile)
    if fn is None:
        raise NotationError(f"unknown notation profile {profile!r}")
    return fn(txt)
