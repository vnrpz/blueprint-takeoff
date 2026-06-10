"""Discovery layer tests (R4 + R6 per-view shim)."""
from src.discovery import ro_to_frame, transform_unit, transform_all
from src.schema import Unit, Panel, RoughOpening


# ---- R6 per-view shim asserts ---------------------------------------------
# Windows: 0.75 total on each dim. Doors: 0.75 w / 0.5 h (threshold).

def test_ro_to_frame_window_default():
    # Window default - symmetric 0.75 on each dim
    assert ro_to_frame(73.25, 89.25) == (72.5, 88.5)
    assert ro_to_frame(36.75, 48.75, kind="window") == (36.0, 48.0)
    assert ro_to_frame(48.75, 60.75, kind="window") == (48.0, 60.0)
    assert ro_to_frame(72.75, 88.5,  kind="window") == (72.0, 87.75)


def test_ro_to_frame_door_threshold():
    # Doors: subtract 0.75 from width, 0.5 from height (threshold = no shim)
    w, h = ro_to_frame(36.75, 80.5, kind="door")
    assert (w, h) == (36.0, 80.0)
    w, h = ro_to_frame(72.75, 80.5, kind="door")
    assert (w, h) == (72.0, 80.0)


def test_ro_to_frame_legacy_shim_override():
    # Legacy: shim_per_side_in overrides per-view defaults symmetrically
    assert ro_to_frame(48.5, 60.5, shim_per_side_in=0.5) == (47.5, 59.5)


# ---- transform_unit honours unit.kind --------------------------------------

def test_transform_unit_window_applies_window_shim():
    u = Unit(unit_id="CM2", kind="window", qty=6,
             panels=[Panel(role="window", width_in=0.0, height_in=0.0)],
             rough_opening=RoughOpening(w_in=36.75, h_in=60.75))
    t = transform_unit(u)
    assert t.panels[0].width_in == 36.0
    assert t.panels[0].height_in == 60.0
    assert u.panels[0].width_in == 0.0  # original untouched


def test_transform_unit_door_applies_door_shim():
    u = Unit(unit_id="DR1", kind="door", qty=4,
             panels=[Panel(role="door", width_in=0.0, height_in=0.0)],
             rough_opening=RoughOpening(w_in=36.75, h_in=80.5))
    t = transform_unit(u)
    assert t.panels[0].width_in == 36.0
    assert t.panels[0].height_in == 80.0


def test_transform_unit_double_door():
    u = Unit(unit_id="DR2", kind="door", qty=2,
             panels=[Panel(role="door", width_in=0.0, height_in=0.0)],
             rough_opening=RoughOpening(w_in=72.75, h_in=80.5))
    t = transform_unit(u)
    assert t.panels[0].width_in == 72.0
    assert t.panels[0].height_in == 80.0


def test_transform_unit_no_ro_passthrough():
    u = Unit(unit_id="W1", kind="window", qty=3,
             panels=[Panel(role="window", width_in=72.5, height_in=88.5)])
    t = transform_unit(u)
    assert t.panels[0].width_in == 72.5
    assert t.panels[0].height_in == 88.5


def test_transform_all_batch_windows():
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
