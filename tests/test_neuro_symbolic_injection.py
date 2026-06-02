"""Integration test (no VLM): neuro-symbolic checkers vs synthetic injections.

Proves the error_recall gate (>= 0.80, TZ §12) is reachable from the
algorithmic layer alone, without any model call. This is the safety net
for handwritten PDFs where the VLM may stumble.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.inject_errors import generate, evaluate_flags
from eval.symbolic_checks import run_all


def _baseline_from_4006() -> dict:
    """Reference sizes from the canonical 4006 ground truth."""
    gt = json.loads(Path("tests/ground_truth/4006.json").read_text(encoding="utf-8"))
    out = {}
    for u in gt["units"]:
        panels = u.get("panels", [])
        if panels:
            out[u["unit_id"]] = {
                "width_in": panels[0]["width_in"],
                "height_in": panels[0]["height_in"],
            }
    return out


def _composite_ref_from_4006() -> dict:
    gt = json.loads(Path("tests/ground_truth/4006.json").read_text(encoding="utf-8"))
    return {u["unit_id"]: len(u.get("panels", []))
            for u in gt["units"] if u.get("kind") == "composite"}


def test_neuro_symbolic_recall_meets_gate():
    baseline = _baseline_from_4006()
    comp_ref = _composite_ref_from_4006()
    variants = generate(source_path="tests/ground_truth/4006.json")
    recalls = []
    for v in variants:
        units = v["data"]["units"]
        plan_only = v["data"].get("plan_only_marks", [])
        findings = run_all(units,
                           plan_only_marks=plan_only,
                           baseline=baseline,
                           composite_panel_ref=comp_ref)
        rep = evaluate_flags(findings, v["injections"])
        recalls.append(rep["recall"])
        # Each variant must hit at least one expected flag.
        if rep["recall"] == 0:
            pytest.fail(f"{v['variant_id']} missed entirely. Findings: {findings}")
    avg = sum(recalls) / len(recalls)
    assert avg >= 0.80, f"avg recall={avg:.2f} fails the 0.80 gate (TZ §12)"


def test_clean_gt_produces_no_flags():
    """The canonical 4006 GT (no injections) should not trigger any flag."""
    gt = json.loads(Path("tests/ground_truth/4006.json").read_text(encoding="utf-8"))
    findings = run_all(gt["units"],
                       baseline=_baseline_from_4006(),
                       composite_panel_ref=_composite_ref_from_4006())
    # Allow at most 0 flags (clean baseline).
    spurious = {uid: fl for uid, fl in findings.items() if fl}
    assert not spurious, f"Clean GT raised spurious flags: {spurious}"
