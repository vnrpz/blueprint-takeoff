"""R5 partial-results compiler.

Scans runs/variant_*/{project}/{model}/units.jsonl artifacts left on disk
from a (possibly cancelled) benchmark, runs eval.metrics.evaluate against
GT, and emits runs/r5_leaderboard.csv with real rows.

Used when run_benchmark.py was SIGTERMed before the in-memory rows could
flush to CSV.
"""
from __future__ import annotations
import csv, json, os, sys
from pathlib import Path
from datetime import datetime

# Late imports so the script can run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.schema import Unit
from eval.metrics import evaluate
from dotenv import load_dotenv
load_dotenv()

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"
GT_EXTRACT = {
    "745": REPO / "tests/ground_truth/745_extract.json",
    "OFR": REPO / "tests/ground_truth/4006_extract.json",  # OFR maps to 4006 offer side
}
GT_OFFER = {
    "745": REPO / "tests/ground_truth/745.json",
    "OFR": REPO / "tests/ground_truth/4006.json",
}

# (variant_letter, name_on_disk)
# Variant E uses VariantB's directory on raster PDFs (suffix _E_fallback_B)
VARIANTS = [
    ("E", "variant_b", "_E_fallback_B"),   # E always raster-fallbacked here
    ("A", "variant_a", ""),
    ("C", "variant_c", ""),
]
MODELS = ["gemini-3.1-pro-preview", "claude-opus-4-7"]
MODEL_FULL = {
    "gemini-3.1-pro-preview": "gemini:gemini-3.1-pro-preview",
    "claude-opus-4-7": "anthropic:claude-opus-4-7",
}
PROJECTS = ["745", "OFR"]

def load_units(p: Path):
    if not p.exists() or p.stat().st_size == 0:
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip(): continue
        try:
            d = json.loads(line)
            out.append(Unit.from_dict(d))
        except Exception as e:
            print(f"  parse error in {p.name}: {e}", file=sys.stderr)
    return out

def load_gt(path: Path):
    if not path.exists(): return []
    raw = json.loads(path.read_text())
    return [Unit.from_dict(u) for u in raw.get("units", [])]

def main():
    rows = []
    for v_letter, dir_name, suffix in VARIANTS:
        for proj in PROJECTS:
            for model in MODELS:
                proj_dir_name = proj + suffix
                jsonl = RUNS / dir_name / proj_dir_name / model / "units.jsonl"
                row = {
                    "variant": v_letter,
                    "model": MODEL_FULL[model],
                    "project": proj,
                    "artifact": str(jsonl.relative_to(REPO)),
                }
                if not jsonl.exists():
                    row["error"] = "no artifact (cell not started or killed before save)"
                    row["status"] = "skipped"
                    rows.append(row); continue
                if jsonl.stat().st_size == 0:
                    row["error"] = "empty units.jsonl (provider returned nothing or invalid JSON each call)"
                    row["status"] = "empty"
                    row["n_units"] = 0
                    rows.append(row); continue
                pred = load_units(jsonl)
                row["n_units"] = sum(u.qty for u in pred)
                row["n_groups"] = len({(u.kind, tuple((p.width_in, p.height_in) for p in u.panels)) for u in pred})
                row["status"] = "ok"
                # Extraction-side GT (745 → 745_extract; OFR → 4006_extract)
                # Skip extraction for OFR/4006 since 4006_extract.json is model-derived (R5 decision)
                if proj == "745":
                    gt = load_gt(GT_EXTRACT["745"])
                    m = evaluate(pred, gt)
                    row.update({"ext_" + k: v for k, v in m.to_dict().items()})
                # Offer-side GT
                if proj in GT_OFFER:
                    gt = load_gt(GT_OFFER[proj])
                    m = evaluate(pred, gt)
                    row.update({"ofr_" + k: v for k, v in m.to_dict().items()})
                rows.append(row)

    # Write CSV
    fields = sorted({k for r in rows for k in r.keys()})
    out_csv = RUNS / "r5_leaderboard.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows: w.writerow(r)
    print(f"Wrote {out_csv} ({len(rows)} rows)")

    # Compact summary
    print("\n=== Summary ===")
    for r in rows:
        e_f1 = r.get("ext_group_f1")
        e_uce = r.get("ext_unit_count_error")
        o_f1 = r.get("ofr_group_f1")
        o_uce = r.get("ofr_unit_count_error")
        n_units = r.get("n_units", "—")
        st = r.get("status", "?")
        e_str = f"ext: f1={e_f1:.3f}/uce={e_uce:.3f}" if e_f1 is not None else "ext: —"
        o_str = f"ofr: f1={o_f1:.3f}/uce={o_uce:.3f}" if o_f1 is not None else "ofr: —"
        print(f"  {r['variant']:1} | {r['model'][:30]:30} | {r['project']:4} | "
              f"n_units={n_units:>4} | {e_str:25} | {o_str:25} | {st}")

if __name__ == "__main__":
    main()
