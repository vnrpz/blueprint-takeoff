"""TZ §13: eval gate on 4006.

Skips if PDFs absent. With perfect predictions (echo GT) the gate must pass —
this is the test we'll re-run once a real pipeline writes a units.jsonl.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import pytest

from src.schema import Unit
from eval.metrics import evaluate

GATE = {
    "unit_count_error": 0.05,
    "group_f1": 0.90,
    "qty_mae": 1.0,
    "glass_acc": 0.95,
    "egress_acc": 0.95,
    "hallucination_rate": 0.05,
}


def _load_gt():
    return json.loads(Path("tests/ground_truth/4006.json").read_text(encoding="utf-8"))


def test_gate_pass_with_oracle_predictions():
    gt_raw = _load_gt()
    gt_units = [Unit.from_dict(u) for u in gt_raw["units"]]
    m = evaluate(gt_units, gt_units, gt_frames_total=gt_raw["totals"]["frames"])
    assert m.unit_count_error <= GATE["unit_count_error"]
    assert m.group_f1 >= GATE["group_f1"]
    assert m.qty_mae <= GATE["qty_mae"]
    assert m.glass_acc >= GATE["glass_acc"]
    assert m.egress_acc >= GATE["egress_acc"]
    assert m.hallucination_rate <= GATE["hallucination_rate"]


def test_gate_fails_when_predictions_corrupt():
    """Sanity: dropping half the units must fail the gate, proving the gate
    is meaningful (not always true)."""
    gt_raw = _load_gt()
    gt_units = [Unit.from_dict(u) for u in gt_raw["units"]]
    bad = gt_units[: len(gt_units) // 2]
    m = evaluate(bad, gt_units, gt_frames_total=gt_raw["totals"]["frames"])
    assert m.unit_count_error > GATE["unit_count_error"] or m.group_f1 < GATE["group_f1"]


@pytest.mark.skipif(not Path("runs/winner_units_4006.jsonl").exists(),
                    reason="No winning pipeline output yet — run eval/run_benchmark first.")
def test_winning_pipeline_meets_gate():
    pred_units = []
    with open("runs/winner_units_4006.jsonl", encoding="utf-8") as f:
        for line in f:
            pred_units.append(Unit.from_dict(json.loads(line)))
    gt_raw = _load_gt()
    gt_units = [Unit.from_dict(u) for u in gt_raw["units"]]
    m = evaluate(pred_units, gt_units, gt_frames_total=gt_raw["totals"]["frames"])
    for k, v in GATE.items():
        actual = getattr(m, k)
        if k in {"unit_count_error", "qty_mae", "hallucination_rate"}:
            assert actual <= v, f"{k}={actual} > {v}"
        else:
            assert actual >= v, f"{k}={actual} < {v}"
