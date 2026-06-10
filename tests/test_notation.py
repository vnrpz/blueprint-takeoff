"""TZ R7 §2 — the deterministic decoder must reproduce the human-verified
745 A-H dimensions from the raw size codes, and handle the documented
examples + explicit literals."""
import json, os, re
import pytest
from src.notation import decode, decode_weather_shield, decode_literal, NotationError

GT = os.path.join(os.path.dirname(__file__), "ground_truth", "745_extract.json")


def _code_of(marks):
    for m in marks:
        if re.match(r"^(?:\d+\s*-\s*)?\d{4}$", str(m).strip()):
            return str(m).strip()
    return None


def test_decoder_matches_745_extract_gt():
    data = json.load(open(GT, encoding="utf-8"))
    checked = 0
    for u in data["units"]:
        code = _code_of(u.get("source_marks", []))
        assert code, f"unit {u['unit_id']}: no size code in {u['source_marks']}"
        d = decode(code, profile="weather_shield")
        p = u["panels"][0]
        assert d.width_in == pytest.approx(p["width_in"]), f"{u['unit_id']} {code}: w {d.width_in} != {p['width_in']}"
        assert d.height_in == pytest.approx(p["height_in"]), f"{u['unit_id']} {code}: h {d.height_in} != {p['height_in']}"
        checked += 1
    assert checked >= 8, f"expected >=8 A-H rows, checked {checked}"


@pytest.mark.parametrize("code,w,h", [
    ("2870", 32, 84), ("3050", 36, 60), ("2856", 32, 66), ("3180", 37, 96),
])
def test_weather_shield_examples(code, w, h):
    d = decode_weather_shield(code)
    assert (d.width_in, d.height_in) == (w, h)


@pytest.mark.parametrize("code,w,h,n", [
    ("2-2870", 64, 84, 2), ("3-2870", 96, 84, 3),
])
def test_weather_shield_composite(code, w, h, n):
    d = decode_weather_shield(code)
    assert (d.width_in, d.height_in, d.mull_count) == (w, h, n)
    assert d.unit_width_in == 32


@pytest.mark.parametrize("lit,w,h", [
    ("2'-8\" x 7'-0\"", 32, 84), ("3'-1\" x 8'-0\"", 37, 96), ("32 x 84", 32, 84),
    ("2'-8\" x 5'-6 1/2\"", 32, 66.5),
])
def test_literals_and_fractions(lit, w, h):
    d = decode_literal(lit)
    assert d.width_in == pytest.approx(w) and d.height_in == pytest.approx(h)


def test_unknown_profile_flags_not_guesses():
    with pytest.raises(NotationError):
        decode("2870", profile="acme_unknown")
