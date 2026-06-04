"""Bipartite matching predicted vs ground-truth (TZ §8).

Both sides are first aggregated into spec-groups by `normalize.group_units`,
then matched with Hungarian (scipy.optimize.linear_sum_assignment) using a
size-distance edge weight inside a tolerance gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Iterable

import numpy as np

from src.schema import Unit
from src.normalize import SpecGroupKey, spec_group_key, group_units


# Size tolerance for matching (inches). Tau = 1.0 per TZ §8.
DEFAULT_TAU_IN = 1.0


@dataclass
class GroupMatch:
    pred_key: Optional[SpecGroupKey]
    gt_key: Optional[SpecGroupKey]
    pred_qty: int
    gt_qty: int
    distance: float  # 0 if exact, in inches summed over panels

    @property
    def is_matched(self) -> bool:
        return self.pred_key is not None and self.gt_key is not None

    @property
    def is_false_positive(self) -> bool:  # predicted but no GT
        return self.pred_key is not None and self.gt_key is None

    @property
    def is_miss(self) -> bool:  # GT but no prediction
        return self.pred_key is None and self.gt_key is not None


def _panel_size_distance(p1: tuple, p2: tuple) -> float:
    """L1 size distance on (role, w, h, glass, u, egress) — sums |w| + |h| if
    same role, else returns inf."""
    role1, w1, h1, *_ = p1
    role2, w2, h2, *_ = p2
    if role1 != role2:
        return float("inf")
    return abs(w1 - w2) + abs(h1 - h2)


def _key_size_distance(a: SpecGroupKey, b: SpecGroupKey) -> float:
    if a.kind != b.kind:
        return float("inf")
    if len(a.panels) != len(b.panels):
        return float("inf")
    # Both panel tuples are sorted in spec_group_key already.
    return sum(_panel_size_distance(p1, p2) for p1, p2 in zip(a.panels, b.panels))


def match_groups(
    pred_groups: Dict[SpecGroupKey, int],
    gt_groups: Dict[SpecGroupKey, int],
    tau_in: float = DEFAULT_TAU_IN,
) -> List[GroupMatch]:
    """Hungarian max-weight bipartite match.

    Edge weight = 1 / (1 + distance) for distance <= tau_in (per-panel),
    else 0 (no edge). Unmatched predicted groups are false positives;
    unmatched GT groups are misses.
    """
    from scipy.optimize import linear_sum_assignment  # lazy

    p_keys = list(pred_groups.keys())
    g_keys = list(gt_groups.keys())
    if not p_keys and not g_keys:
        return []

    # Tau is per-panel; total tolerance scales with panel count.
    def tol_for(a: SpecGroupKey, b: SpecGroupKey) -> float:
        return tau_in * max(len(a.panels), len(b.panels))

    if p_keys and g_keys:
        cost = np.full((len(p_keys), len(g_keys)), 1e9, dtype=float)
        for i, pk in enumerate(p_keys):
            for j, gk in enumerate(g_keys):
                d = _key_size_distance(pk, gk)
                if d <= tol_for(pk, gk):
                    # R3 RELAXATION: glass/u/egress no longer block matching.
                    # Field accuracy is reported separately on matched groups.
                    cost[i, j] = d
        row_ind, col_ind = linear_sum_assignment(cost)
    else:
        row_ind, col_ind = np.array([]), np.array([])

    matched_pred = set()
    matched_gt = set()
    matches: List[GroupMatch] = []
    for r, c in zip(row_ind, col_ind):
        if cost[r, c] >= 1e9:
            continue
        pk, gk = p_keys[r], g_keys[c]
        matches.append(GroupMatch(
            pred_key=pk, gt_key=gk,
            pred_qty=pred_groups[pk], gt_qty=gt_groups[gk],
            distance=float(cost[r, c]),
        ))
        matched_pred.add(r)
        matched_gt.add(c)
    for i, pk in enumerate(p_keys):
        if i in matched_pred:
            continue
        matches.append(GroupMatch(pred_key=pk, gt_key=None,
                                  pred_qty=pred_groups[pk], gt_qty=0, distance=float("inf")))
    for j, gk in enumerate(g_keys):
        if j in matched_gt:
            continue
        matches.append(GroupMatch(pred_key=None, gt_key=gk,
                                  pred_qty=0, gt_qty=gt_groups[gk], distance=float("inf")))
    return matches


def match_units(
    pred: Iterable[Unit], gt: Iterable[Unit], *, tau_in: float = DEFAULT_TAU_IN
) -> List[GroupMatch]:
    return match_groups(group_units(pred), group_units(gt), tau_in=tau_in)
