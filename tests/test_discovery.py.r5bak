"""Discovery layer tests (R4)."""
from src.discovery import ro_to_frame, transform_unit, transform_all
from src.schema import Unit, Panel, RoughOpening


def test_ro_to_frame_default_shim():
    # 0.375 per side → subtract 0.75 from each dim (R5 fix)
    assert ro_to_frame(73.25, 89.25) == (72.5, 88.5)


def test_ro_to_frame_custom_shim():
    assert ro_to_frame(48.5, 60.5, shim_per_side_in=0.5) == (47.5, 59.5)


def test_transform_unit_applies_ro():
    u = Unit(unit_id="CM2", kind="window", qty=6,
             panels=[Panel(role="window", width_in=0.0, height_in=0.0)],
             rough_opening=RoughOpening(w_in=36.75, h_in=60.75))
    t = transform_unit(u)
    assert t.panels[0].width_in == 36.0   # 36.75 - 0.75
    assert t.panels[0].height_in == 60.0
    # Original unit unchanged
    assert u.panels[0].width_in == 0.0


def test_transform_unit_no_ro_passthrough():
    u = Unit(unit_id="W1", kind="window", qty=3,
             panels=[Panel(role="window", width_in=72.5, height_in=88.5)])
    t = transform_unit(u)
    # No RO → unchanged
    assert t.panels[0].width_in == 72.5
    assert t.panels[0].height_in == 88.5


def test_transform_all_batch():
    units = [
        Unit(unit_id=f"U{i}", kind="window", qty=1,
             panels=[Panel(role="window", width_in=0, height_in=0)],
             rough_opening=RoughOpening(w_in=36.75, h_in=48.75))
        for i in range(5)
    ]
    out = transform_all(units)
    for t in out:
        assert t.panels[0].width_in == 36.0
        assert t.panels[0].height_in == 48.0
