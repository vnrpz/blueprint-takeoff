"""Leaderboard runner (TZ §14).

Iterates variants × models × projects. Persists per-run JSON + a combined
runs/leaderboard.csv and runs/leaderboard.html. Winner selection:
max group_f1 with unit_count_error ≤ 0.05, tie-break qty_mae ↓, then cost ↑.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from src.pipelines import VARIANTS
from src.schema import Unit
from src.vlm import get_provider, MockProvider
from eval.metrics import evaluate
from eval.inject_errors import generate as gen_injections, evaluate_flags


PROJECTS = {
    "4006":  "data/raw/blueprint.pdf",
    "OFR":   "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf",
    "745":   "data/raw/745_Tamarack_Trail.pdf",
    "321":   "data/raw/321_Sunset.pdf",
    "1729":  "data/raw/1729_Longvalley.pdf",
    "3122":  "data/raw/3122_Lyndale.pdf",
}

GROUND_TRUTH = {
    "4006": "tests/ground_truth/4006.json",
    "745":  "tests/ground_truth/745.json",
}


def _load_gt_units(path: str) -> List[Unit]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for u in raw.get("units", []):
        out.append(Unit.from_dict(u))
    return out


def _frames_total(gt_path: str) -> Optional[int]:
    raw = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    return raw.get("totals", {}).get("frames")


def _pick_winner(rows: List[Dict]) -> Optional[Dict]:
    cands = [r for r in rows if r.get("project") == "4006" and r.get("unit_count_error", 1.0) <= 0.05]
    if not cands:
        return None
    cands.sort(key=lambda r: (-r.get("group_f1", 0), r.get("qty_mae", 1e9), r.get("cost_usd", 1e9)))
    return cands[0]


def run(variants: List[str], models: List[str], projects: List[str],
        out_csv: str = "runs/leaderboard.csv", out_html: str = "runs/leaderboard.html",
        budget_usd: float = 0.0) -> List[Dict]:
    rows: List[Dict] = []
    spent = 0.0
    for variant_letter in variants:
        Cls = VARIANTS[variant_letter]
        for model_spec in models:
            try:
                provider = get_provider(model_spec)
            except Exception as e:
                rows.append({"variant": variant_letter, "model": model_spec, "project": "*",
                             "error": f"provider init: {e}"})
                continue
            pipeline = Cls(provider)
            for proj in projects:
                pdf = PROJECTS.get(proj)
                if not pdf or not Path(pdf).exists():
                    rows.append({"variant": variant_letter, "model": model_spec, "project": proj,
                                 "error": "pdf missing"})
                    continue
                try:
                    result = pipeline.run(pdf, project=proj)
                except Exception as e:
                    rows.append({"variant": variant_letter, "model": model_spec, "project": proj,
                                 "error": f"{type(e).__name__}: {e}",
                                 "traceback": traceback.format_exc()[:500]})
                    continue
                row = {
                    "variant": variant_letter,
                    "model": model_spec,
                    "project": proj,
                    "elapsed_sec": round(result.elapsed_sec, 2),
                    "cost_usd": round(result.cost_usd, 4),
                    "n_units": sum(u.qty for u in result.units),
                    "n_groups": len({(u.kind, tuple(p.width_in for p in u.panels)) for u in result.units}),
                }
                gt_path = GROUND_TRUTH.get(proj)
                if gt_path and Path(gt_path).exists():
                    gt_units = _load_gt_units(gt_path)
                    metrics = evaluate(result.units, gt_units, gt_frames_total=_frames_total(gt_path))
                    row.update(metrics.to_dict())
                rows.append(row)
                spent += float(row.get("cost_usd") or 0)
                if budget_usd and spent >= budget_usd:
                    rows.append({"variant": "*", "model": "*", "project": "*",
                                 "error": f"budget cap ${budget_usd} hit; spent ${spent:.2f}"})
                    break
            else:
                continue
            break
        else:
            continue
        break
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fields = sorted({k for r in rows for k in r.keys()})
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    _render_html(rows, _pick_winner(rows), out_html)
    return rows


def _render_html(rows: List[Dict], winner: Optional[Dict], path: str) -> None:
    cols = ["variant", "model", "project", "group_f1", "qty_mae", "unit_count_error",
            "glass_acc", "egress_acc", "hallucination_rate", "cost_usd", "elapsed_sec", "error"]
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for r in rows:
        cls = "winner" if winner and all(r.get(k) == winner.get(k) for k in ("variant", "model", "project")) else ""
        cells = "".join(f"<td>{r.get(c, '')}</td>" for c in cols)
        body += f"<tr class=\"{cls}\">{cells}</tr>"
    win_block = ""
    if winner:
        win_block = f"<p><strong>Winner:</strong> Variant {winner['variant']} / {winner['model']} on 4006 — group_f1={winner.get('group_f1', 0):.3f}, qty_mae={winner.get('qty_mae', 0):.2f}.</p>"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>blueprint-takeoff leaderboard</title>
<style>
body{{font-family:system-ui,sans-serif;padding:24px;max-width:1280px;margin:auto}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #ddd;padding:6px 8px;text-align:left}}
th{{background:#f5f5f5}}tr.winner{{background:#e8f5e9;font-weight:600}}
.error{{color:#c00}}
</style></head><body>
<h1>blueprint-takeoff — leaderboard</h1>
{win_block}
<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
</body></html>
"""
    Path(path).write_text(html, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="A,B,C,D,E,F")
    ap.add_argument("--models", default="gemini:gemini-3.1-pro-preview,anthropic:claude-opus-4-7,openai:gpt-5.5,azure:gpt-4o,azure:gpt-4.1-nano")
    ap.add_argument("--projects", default="4006,745,321,1729,3122")
    ap.add_argument("--out-csv", default="runs/leaderboard.csv")
    ap.add_argument("--out-html", default="runs/leaderboard.html")
    ap.add_argument("--budget-usd", type=float, default=0.0, help="Hard cap; 0 = no cap.")
    args = ap.parse_args(argv)
    rows = run(
        variants=args.variants.split(","),
        models=args.models.split(","),
        projects=args.projects.split(","),
        out_csv=args.out_csv, out_html=args.out_html,
        budget_usd=args.budget_usd,
    )
    print(f"Wrote {args.out_csv} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
