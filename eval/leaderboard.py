
"""Task 9 — cross-branch leaderboard. Routes every project PDF, runs its branch,
scores what is scorable, and records honest status for the rest."""
from __future__ import annotations
import json, os, sys, dataclasses, datetime, pathlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.router import route_pdf
from src.branches.vector_table import extract_ofr
from src.branches.raster_vlm import extract_elevations, extract_handwritten
from src.quality import detect_errors, annotate_qty_source

PROJECTS = {
    "745_Tamarack_Trail":  "data/raw/745_Tamarack_Trail.pdf",
    "4006_blueprint":      "data/raw/blueprint.pdf",
    "4006_OFR_offer":      "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf",
    "1729_Longvalley":     "data/raw/1729_Longvalley.pdf",
}


def _row(name, path):
    r = route_pdf(path)
    row = {"project": name, "branch": r.branch, "branch_name": r.name,
           "scored": False, "metrics": {}, "n_units": 0, "quality": {}}
    if r.branch == 2:  # raster-table 745 — scored gate
        gp = "eval/gate_745_result.json"
        if os.path.exists(gp):
            g = json.load(open(gp))
            row["scored"] = True
            row["metrics"] = g.get("metrics", {})
            row["n_units"] = g.get("n_units", 0)
            row["gate_taken"] = g.get("gate_taken")
    elif r.branch == 1:  # OFR vector-table
        ex = extract_ofr(path)
        exd = {"units": [dataclasses.asdict(u) for u in ex.units],
               "recon_detail": ex.recon_detail, "scored": False}
        annotate_qty_source(exd, "price_reconciled")
        row["n_units"] = len(ex.units)
        row["metrics"] = {"total_qty": ex.total_qty, "reconciled": ex.reconciled,
                          "offer_lines": len(ex.recon_detail)}
        row["quality"] = detect_errors(exd)
    elif r.branch == 3:  # elevations
        ex = extract_elevations(path)
        row["n_units"] = len(ex["units"])
        row["metrics"] = {"note": ex["note"]}
        annotate_qty_source(ex, "counted_openings")
        row["quality"] = detect_errors(ex)
    elif r.branch == 4:  # handwritten
        ex = extract_handwritten(path)
        row["n_units"] = len(ex["units"])
        annotate_qty_source(ex, "vlm_read")
        row["quality"] = detect_errors(ex)
        row["metrics"] = {"confidence": ex["confidence"]}
    return row


def main():
    rows = [_row(n, p) for n, p in PROJECTS.items()]
    out = {"generated": datetime.datetime.utcnow().isoformat() + "Z",
           "version": "v8", "rows": rows}
    pathlib.Path("eval").mkdir(exist_ok=True)
    pathlib.Path("eval/leaderboard_v8.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
