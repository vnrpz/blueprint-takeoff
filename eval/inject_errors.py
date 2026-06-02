"""Synthetic error injection (TZ §10).

Takes 4006 ground truth and produces N variants with known defects.
Each defect has an `expected_flag` indicating what flag a correct system
should attach. We measure error_recall / error_precision against this.

Defect types implemented:
1.  SIZE_MISMATCH_SCHEDULE_VS_ELEVATION — schedule says W2=48 3/16x88.5, elevation shows 50x88.5.
2.  TEMPERED_REQUIRED_BUT_ANNEALED     — IRC R308.4: window <24" from a door must be tempered.
3.  EGRESS_FAIL_BEDROOM                — IRC R310: clear opening < 5.7 sqft in a bedroom.
4.  MARK_ON_PLAN_NOT_IN_SCHEDULE       — plan references W9 which isn't in the schedule.
5.  QTY_MISMATCH_FACADE_VS_SCHEDULE    — elevation totals diverge from schedule qty by >1.
6.  SILL_HEIGHT_LESS_THAN_24_NO_TEMP   — sill <18" near floor without TEMP flag.
7.  U_FACTOR_BELOW_ENERGY_TABLE        — quotes U=0.30 but R402.1.1 demands <=0.27.
8.  COMPOSITE_PANEL_COUNT_DROP         — composite U2 reduces 3 panels to 2 in one source.
9.  EGRESS_TRUE_BUT_TEMPERED_REQUIRED  — egress allowed via TEMP exception not declared.
10. MISSING_GLASS_TYPE_ON_TEMP_ZONE    — tempered zone window with glass=null.
"""
from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Injection:
    id: str
    defect_type: str
    target_unit_id: str
    expected_flag: str
    description: str


def _load_4006(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _clone(d: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(d)


def _find(units: List[Dict[str, Any]], uid: str) -> Dict[str, Any]:
    for u in units:
        if u["unit_id"] == uid:
            return u
    raise KeyError(uid)


def generate(seed: int = 17, *, source_path: str | Path = "tests/ground_truth/4006.json"
             ) -> List[Dict[str, Any]]:
    """Generate the canonical 10 injected variants. Each variant:
       {"variant_id", "data", "injections": [Injection]}
    """
    random.seed(seed)
    gt = _load_4006(source_path)
    out: List[Dict[str, Any]] = []

    # 1. SIZE_MISMATCH
    v = _clone(gt)
    u = _find(v["units"], "W2")
    u["panels"][0]["width_in"] = 50.0           # was 48.1875
    out.append({
        "variant_id": "v01_size_mismatch_W2",
        "data": v,
        "injections": [Injection("inj01", "SIZE_MISMATCH_SCHEDULE_VS_ELEVATION", "W2",
            "size_mismatch_schedule_elevation",
            "W2 width changed from 48 3/16 to 50.0 inches.")],
    })

    # 2. TEMPERED_REQUIRED but ANN
    v = _clone(gt)
    u = _find(v["units"], "W4")
    u["panels"][0]["glass"] = "annealed"        # already ANN actually; force into proximity zone
    u["adjacent_door"] = True                   # synthetic geometry hint
    out.append({
        "variant_id": "v02_tempered_required_W4",
        "data": v,
        "injections": [Injection("inj02", "TEMPERED_REQUIRED_BUT_ANNEALED", "W4",
            "irc_r308_4_violation",
            "W4 is adjacent to a door (<24 in) but glass=annealed.")],
    })

    # 3. EGRESS_FAIL_BEDROOM
    v = _clone(gt)
    u = _find(v["units"], "W3")
    u["panels"][0]["clear_opening_sqft"] = 4.5   # below 5.7 sqft minimum
    u["room_label"] = "bedroom"
    out.append({
        "variant_id": "v03_egress_fail_W3",
        "data": v,
        "injections": [Injection("inj03", "EGRESS_FAIL_BEDROOM", "W3",
            "irc_r310_egress_undersize",
            "Bedroom window clear opening 4.5 sqft < 5.7 sqft min.")],
    })

    # 4. MARK_ON_PLAN_NOT_IN_SCHEDULE
    v = _clone(gt)
    v["plan_only_marks"] = ["W9"]               # not in schedule
    out.append({
        "variant_id": "v04_mark_not_in_schedule",
        "data": v,
        "injections": [Injection("inj04", "MARK_ON_PLAN_NOT_IN_SCHEDULE", "W9",
            "mark_missing_from_schedule",
            "Plan references W9 but Window Schedule has no W9 row.")],
    })

    # 5. QTY_MISMATCH_FACADE_VS_SCHEDULE
    v = _clone(gt)
    u = _find(v["units"], "W1")
    u["facade_count"] = 60                       # schedule says 63
    out.append({
        "variant_id": "v05_qty_mismatch_W1",
        "data": v,
        "injections": [Injection("inj05", "QTY_MISMATCH_FACADE_VS_SCHEDULE", "W1",
            "qty_mismatch_facade_schedule",
            "Elevation count 60 ≠ schedule qty 63 for W1.")],
    })

    # 6. SILL_HEIGHT < 24 without TEMP
    v = _clone(gt)
    u = _find(v["units"], "W2")
    u["sill_height_in"] = 12.0
    u["panels"][0]["glass"] = "annealed"
    out.append({
        "variant_id": "v06_low_sill_no_temp",
        "data": v,
        "injections": [Injection("inj06", "SILL_HEIGHT_LESS_THAN_24_NO_TEMP", "W2",
            "irc_r308_4_low_sill_annealed",
            "Sill height 12 in < 18 in with annealed glass.")],
    })

    # 7. U_FACTOR breach
    v = _clone(gt)
    u = _find(v["units"], "W5")
    u["panels"][0]["u_factor"] = 0.30           # was 0.24
    out.append({
        "variant_id": "v07_ufactor_high",
        "data": v,
        "injections": [Injection("inj07", "U_FACTOR_BELOW_ENERGY_TABLE", "W5",
            "ufactor_breaches_r402_1_1",
            "W5 U=0.30 exceeds R402.1.1 climate-zone max 0.27.")],
    })

    # 8. COMPOSITE_PANEL_COUNT_DROP
    v = _clone(gt)
    u = _find(v["units"], "U2")
    u["panels"] = u["panels"][:2]                # drop the door
    out.append({
        "variant_id": "v08_composite_panel_drop",
        "data": v,
        "injections": [Injection("inj08", "COMPOSITE_PANEL_COUNT_DROP", "U2",
            "composite_panel_count_mismatch",
            "U2 composite reduced from 3 panels to 2.")],
    })

    # 9. EGRESS_TRUE_BUT_TEMPERED_REQUIRED
    v = _clone(gt)
    u = _find(v["units"], "W6")
    u["panels"][0]["egress"] = True
    u["panels"][0]["glass"] = "annealed"
    u["tempered_required"] = True              # marker: R308.4 hazard location identified
    out.append({
        "variant_id": "v09_egress_tempered_conflict",
        "data": v,
        "injections": [Injection("inj09", "EGRESS_TRUE_BUT_TEMPERED_REQUIRED", "W6",
            "egress_tempered_conflict",
            "W6 marked egress + annealed where tempered required.")],
    })

    # 10. MISSING_GLASS_TYPE_ON_TEMP_ZONE
    v = _clone(gt)
    u = _find(v["units"], "W7")
    u["panels"][0]["glass"] = None
    u["tempered_zone"] = True
    out.append({
        "variant_id": "v10_missing_glass_temp_zone",
        "data": v,
        "injections": [Injection("inj10", "MISSING_GLASS_TYPE_ON_TEMP_ZONE", "W7",
            "missing_glass_type_tempered_zone",
            "W7 in tempered zone but glass field is null.")],
    })

    return out


def write_all(out_dir: str | Path,
              source_path: str | Path = "tests/ground_truth/4006.json") -> List[Path]:
    """Persist every variant as JSON for downstream pipelines."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    variants = generate(source_path=source_path)
    paths: List[Path] = []
    for v in variants:
        p = out_dir / f"{v['variant_id']}.json"
        p.write_text(json.dumps({
            "variant_id": v["variant_id"],
            "data": v["data"],
            "injections": [inj.__dict__ for inj in v["injections"]],
        }, indent=2), encoding="utf-8")
        paths.append(p)
    return paths


def evaluate_flags(actual_flags_by_unit: Dict[str, List[str]],
                   injections: List[Injection]) -> Dict[str, Any]:
    """Compute (caught, missed, false_flags) for a single variant.

    actual_flags_by_unit: {unit_id: [flag_name, ...]} from the pipeline.
    Returns dict with caught/total + the lists.
    """
    caught, missed, false_flags = [], [], []
    expected = {(inj.target_unit_id, inj.expected_flag) for inj in injections}
    seen_flags: List[tuple] = []
    for uid, flags in actual_flags_by_unit.items():
        for fl in flags:
            seen_flags.append((uid, fl))
    for inj in injections:
        if (inj.target_unit_id, inj.expected_flag) in seen_flags:
            caught.append(inj.id)
        else:
            missed.append(inj.id)
    for uid, fl in seen_flags:
        if (uid, fl) not in expected:
            false_flags.append({"unit_id": uid, "flag": fl})
    return {
        "caught": caught,
        "missed": missed,
        "false_flags": false_flags,
        "recall": (len(caught) / len(injections)) if injections else 1.0,
        "precision": (len(caught) / max(1, len(caught) + len(false_flags))),
    }
