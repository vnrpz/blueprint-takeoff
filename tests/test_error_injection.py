"""TZ §13: error_recall >= 0.80 on a system that flags everything.

We don't have a real pipeline running here (no PDFs yet), so we simulate the
'oracle' detector that returns the injection's expected flag for the right
unit. This pins the inject_errors module's contract.
"""
from __future__ import annotations
import json
from pathlib import Path
from eval.inject_errors import generate, evaluate_flags


def test_generate_produces_ten():
    variants = generate(source_path="tests/ground_truth/4006.json")
    assert len(variants) >= 10
    for v in variants:
        assert v["data"]["totals"]["units"] == 230
        assert v["injections"]


def test_oracle_detector_recall_perfect():
    """An oracle that emits expected flag on the right unit → recall=1.0."""
    variants = generate(source_path="tests/ground_truth/4006.json")
    rs = []
    for v in variants:
        injections = v["injections"]
        actual = {inj.target_unit_id: [inj.expected_flag] for inj in injections}
        rep = evaluate_flags(actual, injections)
        rs.append(rep["recall"])
    avg = sum(rs) / len(rs)
    assert avg == 1.0


def test_silent_detector_recall_zero():
    variants = generate(source_path="tests/ground_truth/4006.json")
    for v in variants:
        rep = evaluate_flags({}, v["injections"])
        assert rep["recall"] == 0.0


def test_partial_detector_meets_gate():
    """80% recall gate: detect 8 / 10 injection variants."""
    variants = generate(source_path="tests/ground_truth/4006.json")
    hits, total = 0, 0
    for i, v in enumerate(variants):
        injections = v["injections"]
        if i < 8:  # detect first 8 only
            actual = {inj.target_unit_id: [inj.expected_flag] for inj in injections}
        else:
            actual = {}
        rep = evaluate_flags(actual, injections)
        hits += rep["recall"]
        total += 1
    assert hits / total >= 0.80
