"""Metrics per TZ §9.

All measures derive from the GroupMatch list produced by matching.match_units.
Field accuracy (glass/u-factor/egress) is computed on matched groups only.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional, Dict

from src.schema import Unit
from .matching import GroupMatch, match_units


@dataclass
class Metrics:
    group_precision: float
    group_recall: float
    group_f1: float
    qty_mae: Optional[float]
    unit_count_error: float
    frame_count_error: Optional[float]
    glass_acc: Optional[float]
    ufactor_acc: Optional[float]
    egress_acc: Optional[float]
    hallucination_rate: float
    miss_rate: float
    matched_groups: int
    fp_groups: int
    fn_groups: int
    pred_units_total: int
    gt_units_total: int

    def to_dict(self) -> Dict:
        return asdict(self)


def _frame_total(units: Iterable[Unit]) -> int:
    return sum(u.qty * max(1, len(u.panels)) for u in units)


def _field_acc(matches: List[GroupMatch], idx: int) -> Optional[float]:
    """Compare one panel field across matched groups. idx maps into tuple
    (role, w, h, glass, u, egress)."""
    total = 0
    hits = 0
    for m in matches:
        if not m.is_matched:
            continue
        for pp, gp in zip(m.pred_key.panels, m.gt_key.panels):
            pv, gv = pp[idx], gp[idx]
            if gv is None:  # GT has no opinion → skip
                continue
            total += 1
            if pv == gv:
                hits += 1
    if total == 0:
        return None
    return hits / total


def evaluate(
    pred: List[Unit], gt: List[Unit], *, gt_frames_total: Optional[int] = None
) -> Metrics:
    matches = match_units(pred, gt)
    matched = [m for m in matches if m.is_matched]
    fps = [m for m in matches if m.is_false_positive]
    fns = [m for m in matches if m.is_miss]

    pred_groups_total = len(matched) + len(fps)
    gt_groups_total = len(matched) + len(fns)

    precision = (len(matched) / pred_groups_total) if pred_groups_total else 0.0
    recall    = (len(matched) / gt_groups_total) if gt_groups_total else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    qty_mae = (sum(abs(m.pred_qty - m.gt_qty) for m in matched) / len(matched)) if matched else None

    pred_total = sum(m.pred_qty for m in matched) + sum(m.pred_qty for m in fps)
    gt_total   = sum(m.gt_qty   for m in matched) + sum(m.gt_qty   for m in fns)
    unit_count_error = abs(pred_total - gt_total) / gt_total if gt_total else 0.0

    frame_err = None
    if gt_frames_total:
        pred_frames = _frame_total(pred)
        frame_err = abs(pred_frames - gt_frames_total) / gt_frames_total

    halluc_rate = (len(fps) / pred_groups_total) if pred_groups_total else 0.0
    miss_rate   = (len(fns) / gt_groups_total) if gt_groups_total else 0.0

    return Metrics(
        group_precision=precision,
        group_recall=recall,
        group_f1=f1,
        qty_mae=qty_mae,
        unit_count_error=unit_count_error,
        frame_count_error=frame_err,
        glass_acc=_field_acc(matches, 3),
        ufactor_acc=_field_acc(matches, 4),
        egress_acc=_field_acc(matches, 5),
        hallucination_rate=halluc_rate,
        miss_rate=miss_rate,
        matched_groups=len(matched),
        fp_groups=len(fps),
        fn_groups=len(fns),
        pred_units_total=pred_total,
        gt_units_total=gt_total,
    )


def discovery_gap_recall(predicted_gaps: List[str], gt_gap_ids: List[str]) -> float:
    if not gt_gap_ids:
        return 1.0
    found = sum(1 for g in gt_gap_ids if g in set(predicted_gaps))
    return found / len(gt_gap_ids)


def error_detection_scores(
    flagged_injections: List[bool], all_flags: List[bool]
) -> Dict[str, float]:
    """Compute error_recall and error_precision for synthetic injection.

    flagged_injections[i]: did the system flag injection i? (recall denom)
    all_flags[i]:          was flag i a real injection? (precision denom)
    """
    er = (sum(flagged_injections) / len(flagged_injections)) if flagged_injections else 0.0
    ep = (sum(all_flags) / len(all_flags)) if all_flags else 0.0
    return {"error_recall": er, "error_precision": ep}
