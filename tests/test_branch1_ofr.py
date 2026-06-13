"""Branch-1 (OFR vector-table) tests.

Two layers:

* Pure-logic tests run everywhere — they exercise the parsing/normalization and
  the ``to_schema`` mapping on synthetic inputs, with no PDF and no network.
* The end-to-end tests run only when the real (gitignored) offer PDF is present;
  otherwise they skip, matching the repo-wide contract in ``conftest.require_pdf``.
"""
from tests.conftest import require_pdf

from src.branches.vector_table import (
    OfrExtract,
    OfrUnit,
    _frac_to_float,
    _glass_kind,
    _parse_qty_price,
    extract_ofr,
    to_schema,
)

OFR_REL = "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf"


# ---------------------------------------------------------------- pure logic

def test_frac_to_float():
    assert _frac_to_float('72 1/2"') == 72.5
    assert _frac_to_float("36 3/16") == 36.1875
    assert _frac_to_float("48") == 48.0


def test_glass_kind():
    assert _glass_kind("... TEMP glass ...") == "tempered"
    assert _glass_kind("... ANN glass ...") == "annealed"
    assert _glass_kind("TEMP and ANN both") == "mixed"
    assert _glass_kind("no marker here") == "unknown"


def test_parse_qty_price_block():
    # Shape that _PRICEBLOCK_RX expects: item / price / - / unit_price / - / qty / line_total / total
    block = "7\n1,000.00\n-\n250.00\n-\n4\n1,000.00\n1,000.00\nAccessories"
    item_no, unit_price, line_total, qty = _parse_qty_price(block)
    assert item_no == "7"
    assert unit_price == 250.00
    assert qty == 4
    assert line_total == 1000.00
    # economics reconcile
    assert abs(unit_price * qty - line_total) < 0.5


def test_to_schema_shape_synthetic():
    ex = OfrExtract(
        units=[
            OfrUnit(item="1", frame_w=36.0, frame_h=60.0, ro_w=36.5, ro_h=60.5,
                    qty=4, glass="tempered", egress=True,
                    unit_price=250.0, line_total=1000.0),
        ],
        total_qty=4,
        reconciled=True,
    )
    sch = to_schema(ex)
    assert sch["groups"] and sch["groups"][0]["units"]
    u = sch["groups"][0]["units"][0]
    for k in ("mark", "width", "height", "qty", "glass", "egress"):
        assert k in u
    assert sch["total_qty"] == 4
    assert sch["reconciled"] is True


# ---------------------------------------------------------------- end-to-end (needs real PDF)

def test_ofr_reconciles():
    path = require_pdf(OFR_REL)
    ex = extract_ofr(path)
    assert ex.units, "no units extracted"
    assert ex.reconciled, f"reconciliation failed: {ex.recon_detail}"
    for d in ex.recon_detail:
        assert abs(d["unit_price"] * d["qty"] - d["line_total"]) < 0.5, d


def test_ofr_schema_shape():
    path = require_pdf(OFR_REL)
    sch = to_schema(extract_ofr(path))
    assert sch["groups"] and sch["groups"][0]["units"]
    u = sch["groups"][0]["units"][0]
    for k in ("mark", "width", "height", "qty", "glass", "egress"):
        assert k in u
    assert sch["total_qty"] > 0


if __name__ == "__main__":
    test_frac_to_float(); test_glass_kind(); test_parse_qty_price_block()
    test_to_schema_shape_synthetic()
    print("branch1 pure-logic tests PASS")
