import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.branches.vector_table import extract_ofr, to_schema

OFR = "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf"

def test_ofr_reconciles():
    ex = extract_ofr(OFR)
    assert ex.units, "no units extracted"
    assert ex.reconciled, f"reconciliation failed: {ex.recon_detail}"
    # every offer line: unit_price * qty == line_total
    for d in ex.recon_detail:
        assert abs(d["unit_price"] * d["qty"] - d["line_total"]) < 0.5, d

def test_ofr_schema_shape():
    sch = to_schema(extract_ofr(OFR))
    assert sch["groups"] and sch["groups"][0]["units"]
    u = sch["groups"][0]["units"][0]
    for k in ("mark","width","height","qty","glass","egress"):
        assert k in u
    assert sch["total_qty"] > 0

if __name__ == "__main__":
    test_ofr_reconciles(); test_ofr_schema_shape(); print("branch1 tests PASS")
