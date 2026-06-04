"""TZ §13: Hungarian matching + size-tolerance + mirror collapse + dedup."""
from __future__ import annotations
from src.schema import Unit, Panel
from eval.matching import match_units, DEFAULT_TAU_IN


def _w(uid, w, h, qty=1, u=None, egress=None, glass=None):
    return Unit(unit_id=uid, kind="window", qty=qty, panels=[
        Panel(role="window", width_in=w, height_in=h, u_factor=u, egress=egress, glass=glass)
    ])


def test_match_exact_pair():
    pred = [_w("p1", 72.5, 88.5, qty=63, u=0.24, egress=True, glass="mixed")]
    gt = [_w("W1", 72.5, 88.5, qty=63, u=0.24, egress=True, glass="mixed")]
    matches = match_units(pred, gt)
    assert len([m for m in matches if m.is_matched]) == 1
    m = [m for m in matches if m.is_matched][0]
    assert m.pred_qty == 63 and m.gt_qty == 63 and m.distance == 0.0


def test_match_within_tau():
    """0.5in off is inside tau=1.0 → still matched."""
    pred = [_w("p1", 72.5, 88.0, qty=63, u=0.24, egress=True, glass="mixed")]
    gt = [_w("W1", 72.5, 88.5, qty=63, u=0.24, egress=True, glass="mixed")]
    assert any(m.is_matched for m in match_units(pred, gt))


def test_match_outside_tau_is_fp_and_fn():
    pred = [_w("p1", 72.5, 95.0, qty=63, u=0.24, egress=True, glass="mixed")]
    gt = [_w("W1", 72.5, 88.5, qty=63, u=0.24, egress=True, glass="mixed")]
    matches = match_units(pred, gt)
    assert any(m.is_false_positive for m in matches)
    assert any(m.is_miss for m in matches)


def test_match_glass_disagreement_allows_match_but_lowers_field_acc():
    """R3 RELAXATION: glass disagreement does NOT block matching anymore.
    The match happens on (kind, w, h) and glass_acc captures the disagreement
    on the matched subset. Test pins the new contract."""
    from eval.metrics import evaluate
    pred = [_w("p1", 72.5, 88.5, qty=63, u=0.24, egress=True, glass="annealed")]
    gt   = [_w("W1", 72.5, 88.5, qty=63, u=0.24, egress=True, glass="mixed")]
    matches = match_units(pred, gt)
    # Should now match
    assert sum(1 for m in matches if m.is_matched) == 1
    # And glass_acc should reflect the disagreement
    m = evaluate(pred, gt)
    assert m.glass_acc == 0.0   # 0/1 panels glass matched
    assert m.group_f1 == 1.0    # but dimensional matching is perfect


def test_mirror_dedup_in_aggregation():
    """Two units with swapped panel order should aggregate as one group."""
    pred = [
        Unit(unit_id="L", kind="composite", qty=2, panels=[
            Panel(role="window", width_in=36.1875, height_in=96.0, u_factor=0.23),
            Panel(role="door",   width_in=36.1875, height_in=96.0, u_factor=0.23, egress=True),
        ]),
        Unit(unit_id="R", kind="composite", qty=3, panels=[
            Panel(role="door",   width_in=36.1875, height_in=96.0, u_factor=0.23, egress=True),
            Panel(role="window", width_in=36.1875, height_in=96.0, u_factor=0.23),
        ]),
    ]
    gt = [Unit(unit_id="U1", kind="composite", qty=5, panels=[
        Panel(role="window", width_in=36.1875, height_in=96.0, u_factor=0.23),
        Panel(role="door",   width_in=36.1875, height_in=96.0, u_factor=0.23, egress=True),
    ])]
    matches = match_units(pred, gt)
    matched = [m for m in matches if m.is_matched]
    assert len(matched) == 1
    assert matched[0].pred_qty == 5
    assert matched[0].gt_qty == 5
