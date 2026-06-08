"""R6 benchmark: Variants E, A, C × {Gemini 3.1 Pro, claude-opus-4-8} on 745.

Each (variant, model) runs ONCE, producing extracted units. From the same
units we score:
  * extraction = result.units vs tests/ground_truth/745_extract.json
  * offer      = discovery.transform_all(result.units) vs tests/ground_truth/745.json

Outputs:
  runs/leaderboard_<variant>_<model_safe>_<level>.csv  (per-cell partials)
  runs/r6/units_<variant>_<model_safe>.jsonl           (raw extraction)
  runs/r6/r6_run.log                                   (progress)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List

# Ensure repo root on path
sys.path.insert(0, "/root/blueprint-takeoff")

from dotenv import dotenv_values
env = dotenv_values("/root/blueprint-takeoff/.env")
os.environ.update({k: v for k, v in env.items() if v})

from src.pipelines import VARIANTS
from src.schema import Unit
from src.vlm import get_provider
from src.discovery import transform_all
from eval.metrics import evaluate
from eval.run_benchmark import (
    PROJECTS, GROUND_TRUTH_EXTRACTION, GROUND_TRUTH_OFFER,
    _load_gt_units, _frames_total, _write_csv, _safe_id,
)

ROOT = Path("/root/blueprint-takeoff")
RUN_DIR = ROOT / "runs" / "r6"
RUN_DIR.mkdir(parents=True, exist_ok=True)
LOG = RUN_DIR / "r6_run.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def units_to_jsonl(units: List[Unit], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for u in units:
            f.write(json.dumps(u.to_dict(), ensure_ascii=False) + "\n")


def score_extraction(units: List[Unit], proj: str) -> Dict:
    gt_path = GROUND_TRUTH_EXTRACTION.get(proj)
    if not gt_path or not Path(gt_path).exists():
        return {}
    gt = _load_gt_units(gt_path)
    m = evaluate(units, gt, gt_frames_total=_frames_total(gt_path))
    return m.to_dict()


def score_offer(units: List[Unit], proj: str) -> Dict:
    gt_path = GROUND_TRUTH_OFFER.get(proj)
    if not gt_path or not Path(gt_path).exists():
        return {}
    gt = _load_gt_units(gt_path)
    transformed = transform_all(units)
    m = evaluate(transformed, gt, gt_frames_total=_frames_total(gt_path))
    return m.to_dict()


def run_cell(variant_letter: str, model_spec: str, project: str) -> List[Dict]:
    log(f"=== variant={variant_letter} model={model_spec} project={project} ===")
    pdf = PROJECTS.get(project)
    if not pdf or not Path(pdf).exists():
        log(f"PDF missing for {project}")
        return [{"variant": variant_letter, "model": model_spec, "project": project,
                 "gt_level": "extraction", "error": "pdf missing"}]

    try:
        provider = get_provider(model_spec)
    except Exception as e:
        log(f"provider init failed: {e}")
        return [{"variant": variant_letter, "model": model_spec, "project": project,
                 "gt_level": "extraction",
                 "error": f"provider init: {e}",
                 "traceback": traceback.format_exc()[:500]}]

    Cls = VARIANTS[variant_letter]
    pipeline = Cls(provider)

    try:
        result = pipeline.run(pdf, project=project)
    except Exception as e:
        log(f"pipeline failed: {type(e).__name__}: {e}")
        return [{"variant": variant_letter, "model": model_spec, "project": project,
                 "gt_level": "extraction",
                 "error": f"{type(e).__name__}: {e}",
                 "traceback": traceback.format_exc()[:500]}]

    n_units = sum(u.qty for u in result.units)
    n_groups = len({(u.kind, tuple(p.width_in for p in u.panels)) for u in result.units})
    cost = round(result.cost_usd, 4)
    elapsed = round(result.elapsed_sec, 2)
    errs = result.errors or []
    log(f"  units={len(result.units)} qty={n_units} groups={n_groups} cost=${cost} elapsed={elapsed}s "
        f"errors={len(errs)}")
    if errs:
        log(f"  first errors: {errs[:3]}")

    # Persist units
    unit_jsonl = RUN_DIR / f"units_{_safe_id(variant_letter)}_{_safe_id(model_spec)}.jsonl"
    units_to_jsonl(result.units, unit_jsonl)

    base = {
        "variant": variant_letter,
        "model": model_spec,
        "project": project,
        "elapsed_sec": elapsed,
        "cost_usd": cost,
        "n_units": n_units,
        "n_groups": n_groups,
        "errors_count": len(errs),
        "first_error": (errs[0][:300] if errs else None),
    }

    rows = []
    # Extraction
    row_e = {**base, "gt_level": "extraction"}
    metrics_e = score_extraction(result.units, project)
    row_e.update(metrics_e)
    rows.append(row_e)
    log(f"  extraction: group_f1={metrics_e.get('group_f1')} qty_mae={metrics_e.get('qty_mae')} "
        f"unit_count_error={metrics_e.get('unit_count_error')}")
    # Offer (with discovery transform)
    row_o = {**base, "gt_level": "offer"}
    metrics_o = score_offer(result.units, project)
    row_o.update(metrics_o)
    rows.append(row_o)
    log(f"  offer:      group_f1={metrics_o.get('group_f1')} qty_mae={metrics_o.get('qty_mae')} "
        f"unit_count_error={metrics_o.get('unit_count_error')}")
    return rows


def main():
    cells = [
        ("E", "gemini:gemini-3.1-pro-preview", "745"),
        ("E", "anthropic:claude-opus-4-8",     "745"),
        ("A", "gemini:gemini-3.1-pro-preview", "745"),
        ("A", "anthropic:claude-opus-4-8",     "745"),
        ("C", "gemini:gemini-3.1-pro-preview", "745"),
        ("C", "anthropic:claude-opus-4-8",     "745"),
    ]
    log(f"=== R6 BENCHMARK START: {len(cells)} cells ===")
    all_rows: List[Dict] = []
    for v, m, p in cells:
        try:
            rows = run_cell(v, m, p)
        except Exception as e:
            log(f"cell crashed: {type(e).__name__}: {e}")
            rows = [{"variant": v, "model": m, "project": p, "gt_level": "extraction",
                     "error": f"cell crash: {type(e).__name__}: {e}",
                     "traceback": traceback.format_exc()[:500]}]
        all_rows.extend(rows)
        # Per-cell partial CSV (extraction + offer rows for this cell)
        partial = ROOT / "runs" / f"leaderboard_r6_{_safe_id(v)}_{_safe_id(m)}.csv"
        _write_csv(rows, str(partial))
        log(f"  wrote {partial}")

    # Persist combined R6 view
    combined = ROOT / "runs" / "r6_leaderboard.csv"
    _write_csv(all_rows, str(combined))
    log(f"=== R6 BENCHMARK DONE — wrote {combined} ({len(all_rows)} rows) ===")


if __name__ == "__main__":
    main()
