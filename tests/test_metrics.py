"""TZ §13: metric formulas on a fully synthetic mini case."""
from __future__ import annotations
import json
from pathlib import Path
from src.schema import Unit, Panel
from eval.metrics import evaluate, discovery_gap_recall, error_detection_scores


def _w(uid, w, h, qty=1, u=None, egress=None, glass=None):
    return Unit(unit_id=uid, kind="window", qty=qty, panels=[
        Panel(role="window", width_in=w, height_in=h, u_factor=u, egress=egress, glass=glass)
    ])


def test_perfect_match_metrics():
    gt = [_w("W1", 72.5, 88.5, qty=10, u=0.24, egress=True, glass="mixed"),
          _w("W2", 48.1875, 88.5, qty=5, u=0.24, egress=True, glass="mixed")]
    pred = [_w("p1", 72.5, 88.5, qty=10, u=0.24, egress=True, glass="mixed"),
            _w("p2", 48.1875, 88.5, qty=5, u=0.24, egress=True, glass="mixed")]
    m = evaluate(pred, gt)
    assert m.group_f1 == 1.0
    assert m.qty_mae == 0.0
    assert m.unit_count_error == 0.0
    assert m.hallucination_rate == 0.0
    assert m.miss_rate == 0.0


def test_partial_match_metrics():
    gt = [_w("W1", 72.5, 88.5, qty=10, u=0.24, egress=True, glass="mixed"),
          _w("W2", 48.1875, 88.5, qty=5, u=0.24, egress=True, glass="mixed")]
    pred = [_w("p1", 72.5, 88.5, qty=12, u=0.24, egress=True, glass="mixed"),  # qty off by 2
            _w("p2", 99.0, 88.5, qty=3, u=0.24, egress=True, glass="mixed")]    # FP, FN(W2)
    m = evaluate(pred, gt)
    assert m.group_precision == 0.5
    assert m.group_recall == 0.5
    assert m.qty_mae == 2.0
    # unit_count_error = abs((12+3) - (10+5)) / 15 = 0
    assert m.unit_count_error == 0.0
    assert m.fp_groups == 1
    assert m.fn_groups == 1


def test_discovery_gap_recall():
    assert discovery_gap_recall(["hardware_model"], ["hardware_model", "screen_color"]) == 0.5
    assert discovery_gap_recall([], []) == 1.0


def test_error_detection_scores():
    s = error_detection_scores(flagged_injections=[True, True, False],
                               all_flags=[True, True, False, True])
    assert round(s["error_recall"], 3) == 0.667
    assert round(s["error_precision"], 3) == 0.75


def test_metrics_against_4006_self():
    """Loading 4006 GT through the same Unit shape must score 1.0 against itself."""
    raw = json.loads(Path("tests/ground_truth/4006.json").read_text(encoding="utf-8"))
    units = [Unit.from_dict(u) for u in raw["units"]]
    m = evaluate(units, units, gt_frames_total=raw["totals"]["frames"])
    assert m.group_f1 == 1.0
    assert m.unit_count_error == 0.0
    assert m.gt_units_total == 230
