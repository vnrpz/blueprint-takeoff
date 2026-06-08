"""Merge per-run leaderboard CSVs into a canonical runs/leaderboard.csv.

Reads runs/leaderboard_*.csv (excluding the canonical file), dedups by
(variant, model, project, gt_level) keeping the row from the
most-recently-modified file, unions the column sets, and writes:
  - runs/leaderboard.csv (the canonical)
  - runs/leaderboard.html (rendered)

Idempotent. Safe to run after any partial sweep.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path
from typing import Dict, List

from eval.run_benchmark import _render_html, _pick_winner


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--canonical-csv", default="runs/leaderboard.csv")
    ap.add_argument("--canonical-html", default="runs/leaderboard.html")
    ap.add_argument("--measure-project", default="745")
    ap.add_argument("--gt-level", default="extraction")
    args = ap.parse_args(argv)

    rd = Path(args.runs_dir)
    if not rd.exists():
        print(f"no runs dir at {rd}")
        return 1

    canonical = Path(args.canonical_csv).resolve()
    partials: List[Path] = []
    for p in rd.glob("leaderboard_*.csv"):
        if p.resolve() == canonical:
            continue
        partials.append(p)
    partials.sort(key=lambda p: p.stat().st_mtime)
    if not partials:
        print("no partial leaderboard_*.csv files found")
        return 1

    merged: Dict[tuple, Dict] = {}
    fields_all = set()
    for p in partials:
        with p.open(newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            fields_all.update(r.fieldnames or [])
            for row in r:
                key = (row.get("variant"), row.get("model"), row.get("project"), row.get("gt_level"))
                merged[key] = row  # later partials win (sorted by mtime ASC)

    rows = list(merged.values())
    # Cast numeric fields if possible
    for row in rows:
        for k, v in list(row.items()):
            if v in ("", None):
                continue
            try:
                if "." in str(v) or "e" in str(v).lower():
                    row[k] = float(v)
                else:
                    row[k] = int(v)
            except (ValueError, TypeError):
                pass

    fields = sorted(fields_all)
    with canonical.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    win = _pick_winner(rows, measure_project=args.measure_project, gt_level=args.gt_level)
    _render_html(rows, win, args.canonical_html,
                 measure_project=args.measure_project, gt_level=args.gt_level)
    print(f"Merged {len(partials)} partials → {canonical} ({len(rows)} rows, {len(fields)} cols)")
    if win:
        print(f"Winner: variant={win.get('variant')} model={win.get('model')} "
              f"f1={win.get('group_f1')} qty_mae={win.get('qty_mae')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
