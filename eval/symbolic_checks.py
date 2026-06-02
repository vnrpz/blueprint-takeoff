"""Neuro-symbolic checkers (TZ §11).

Pure-Python algorithmic rules. No VLM. Operate on a dict-shaped "augmented
unit" (the same shape ground truth uses, with optional extras like
`sill_height_in`, `adjacent_door`, `room_label`, `facade_count`, `tempered_zone`).

Each checker returns a list of (unit_id, flag_name) tuples for issues it
detects. The collective output goes through `eval.inject_errors.evaluate_flags`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _panels(u: Dict[str, Any]) -> list[Dict[str, Any]]:
    return u.get("panels") or []


def check_r310_egress(units: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """IRC R310: clear opening must be >= 5.7 sqft when egress is required."""
    out = []
    for u in units:
        is_bedroom = (u.get("room_label") or "").lower() == "bedroom"
        for p in _panels(u):
            if p.get("egress") or is_bedroom:
                co = p.get("clear_opening_sqft")
                if co is not None and co < 5.7:
                    out.append((u["unit_id"], "irc_r310_egress_undersize"))
    return out


def check_r308_4_tempered(units: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """IRC R308.4 (selected hazard locations):
    - Glass adjacent to a door (<24 in) must be tempered.
    - Glass with sill height < 18 in must be tempered.
    - Annealed in an explicit tempered_zone must be flagged."""
    out = []
    for u in units:
        adj = bool(u.get("adjacent_door"))
        sill = u.get("sill_height_in")
        zone = bool(u.get("tempered_zone"))
        for p in _panels(u):
            glass = p.get("glass")
            if adj and glass == "annealed":
                out.append((u["unit_id"], "irc_r308_4_violation"))
            if sill is not None and sill < 18 and glass == "annealed":
                out.append((u["unit_id"], "irc_r308_4_low_sill_annealed"))
            if zone and glass is None:
                out.append((u["unit_id"], "missing_glass_type_tempered_zone"))
            if u.get("tempered_required") and glass == "annealed":
                out.append((u["unit_id"], "egress_tempered_conflict"))
    return out


def check_qty_facade_vs_schedule(units: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """If a unit carries a `facade_count` derived from elevation views and
    that count differs from the schedule qty by more than 1 → flag."""
    out = []
    for u in units:
        fc = u.get("facade_count")
        if fc is None:
            continue
        if abs(int(fc) - int(u.get("qty", 0))) > 1:
            out.append((u["unit_id"], "qty_mismatch_facade_schedule"))
    return out


def check_mark_not_in_schedule(units: List[Dict[str, Any]],
                                plan_only_marks: List[str]) -> List[Tuple[str, str]]:
    """If a plan references a mark that is absent from the schedule → flag."""
    schedule_marks = {u["unit_id"] for u in units}
    out = []
    for m in plan_only_marks or []:
        if m not in schedule_marks:
            out.append((m, "mark_missing_from_schedule"))
    return out


def check_composite_panel_count(units: List[Dict[str, Any]],
                                 reference: Dict[str, int] | None = None) -> List[Tuple[str, str]]:
    """Composite assembly must have >= 2 panels. If a reference is given
    (unit_id -> expected_panel_count), mismatch is flagged."""
    out = []
    for u in units:
        if u.get("kind") != "composite":
            continue
        n = len(_panels(u))
        if n < 2:
            out.append((u["unit_id"], "composite_panel_count_mismatch"))
            continue
        if reference and u["unit_id"] in reference:
            if n != reference[u["unit_id"]]:
                out.append((u["unit_id"], "composite_panel_count_mismatch"))
    return out


def check_size_mismatch_vs_baseline(units: List[Dict[str, Any]],
                                     baseline: Dict[str, Dict[str, float]],
                                     tol_in: float = 1.0) -> List[Tuple[str, str]]:
    """Compare each unit's first-panel size to a baseline reference. Flag
    when size differs by more than tol_in."""
    out = []
    for u in units:
        b = baseline.get(u["unit_id"])
        if not b:
            continue
        if not _panels(u):
            continue
        p0 = _panels(u)[0]
        dw = abs(p0.get("width_in", 0) - b.get("width_in", 0))
        dh = abs(p0.get("height_in", 0) - b.get("height_in", 0))
        if dw > tol_in or dh > tol_in:
            out.append((u["unit_id"], "size_mismatch_schedule_elevation"))
    return out


def check_ufactor_breach(units: List[Dict[str, Any]],
                          climate_zone_max: float = 0.27) -> List[Tuple[str, str]]:
    """R402.1.1 (energy table): U-factor must be <= climate-zone max."""
    out = []
    for u in units:
        for p in _panels(u):
            uf = p.get("u_factor")
            if uf is not None and uf > climate_zone_max + 1e-9:
                out.append((u["unit_id"], "ufactor_breaches_r402_1_1"))
    return out


def run_all(units: List[Dict[str, Any]], *,
            plan_only_marks: List[str] | None = None,
            baseline: Dict[str, Dict[str, float]] | None = None,
            composite_panel_ref: Dict[str, int] | None = None,
            climate_zone_max: float = 0.27,
            ) -> Dict[str, List[str]]:
    """Run every checker and return {unit_id: [flag_names]}."""
    findings: Dict[str, List[str]] = {}
    for uid, fl in (
        check_r310_egress(units)
        + check_r308_4_tempered(units)
        + check_qty_facade_vs_schedule(units)
        + check_mark_not_in_schedule(units, plan_only_marks or [])
        + check_composite_panel_count(units, composite_panel_ref)
        + check_size_mismatch_vs_baseline(units, baseline or {})
        + check_ufactor_breach(units, climate_zone_max=climate_zone_max)
    ):
        findings.setdefault(uid, [])
        if fl not in findings[uid]:
            findings[uid].append(fl)
    return findings
