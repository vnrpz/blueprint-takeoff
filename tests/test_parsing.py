"""TZ §13: fraction parsing + spec-group key shape (no PDF needed)."""
from __future__ import annotations
import pytest
from src.normalize import parse_inches, round_dim, spec_group_key, group_units, ufactor_bucket
from src.schema import Unit, Panel
from src.pipelines.parsing import parse_units


def test_parse_inches_decimal():
    assert parse_inches("72") == 72.0
    assert parse_inches("72.5") == 72.5
    assert parse_inches(36.1875) == 36.1875


def test_parse_inches_fractions():
    assert parse_inches("72 1/2") == 72.5
    assert parse_inches("36 3/16") == 36.1875
    assert parse_inches("48 3/16") == 48.1875
    assert parse_inches("1/2") == 0.5


def test_parse_inches_strips_quotes():
    assert parse_inches('72 1/2"') == 72.5
    assert parse_inches('36 3/16"') == 36.1875


def test_parse_inches_rejects_garbage():
    with pytest.raises(ValueError):
        parse_inches("foo")
    with pytest.raises(ValueError):
        parse_inches("")


def test_round_dim_and_ufactor_bucket():
    assert round_dim(48.1875, 0.5) == 48.0
    assert round_dim(48.4, 0.5) == 48.5
    assert ufactor_bucket(0.234) == "0.23"
    assert ufactor_bucket(None) is None


def test_spec_group_mirror_folding():
    """Composite ordered [door, window] vs [window, door] must collapse."""
    a = Unit(unit_id="A", kind="composite", qty=1, panels=[
        Panel(role="window", width_in=36.1875, height_in=96.0, u_factor=0.23),
        Panel(role="door",   width_in=36.1875, height_in=96.0, u_factor=0.23),
    ])
    b = Unit(unit_id="B", kind="composite", qty=2, panels=[
        Panel(role="door",   width_in=36.1875, height_in=96.0, u_factor=0.23),
        Panel(role="window", width_in=36.1875, height_in=96.0, u_factor=0.23),
    ])
    assert spec_group_key(a) == spec_group_key(b)
    agg = group_units([a, b])
    assert sum(agg.values()) == 3
    assert len(agg) == 1


def test_parse_units_tolerates_bad_rows():
    parsed = parse_units([
        {"unit_id": "W1", "kind": "window",
         "panels": [{"role": "window", "width_in": "72 1/2", "height_in": 88.5}],
         "qty": 5},
        "not a dict",
        {"unit_id": "broken", "kind": "window", "panels": []},  # no panels → dropped
        {"unit_id": "W2", "kind": "window",
         "panels": [{"role": "window", "width_in": "48 3/16", "height_in": "88.5"}],
         "qty": "10"},
    ])
    assert len(parsed) == 2
    assert parsed[0].panels[0].width_in == 72.5
    assert parsed[1].qty == 10
