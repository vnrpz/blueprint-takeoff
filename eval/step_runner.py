"""Sandbox-friendly step runner: process N pages of one (variant, project, model)
per invocation, append to runs/.../units.jsonl. Designed to dodge 45-s shell timeouts.

Usage:
    python -m eval.step_runner <variant> <project> <model_spec> <pages_csv>
    e.g.
    python -m eval.step_runner A 4006 azure:gpt-4.1-nano 91,75,93,94
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

from src.credentials import _load_dotenv
_load_dotenv()

from src.pdf_utils import rasterize
from src.vlm import get_provider
from src.pipelines.base import EXTRACTION_PROMPT
from src.pipelines.parsing import parse_units


PROJECTS = {
    "4006":  "data/raw/blueprint.pdf",
    "745":   "data/raw/745_Tamarack_Trail.pdf",
    "321":   "data/raw/321_Sunset.pdf",
    "1729":  "data/raw/1729_Longvalley.pdf",
    "3122":  "data/raw/3122_Lyndale.pdf",
    "OFR":   "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf",
}


def main(argv) -> int:
    if len(argv) < 5:
        print("usage: step_runner.py <variant> <project> <model> <pages_csv>")
        return 2
    variant = argv[1]
    project = argv[2]
    model = argv[3]
    pages = sorted({int(x) - 1 for x in argv[4].split(",") if x.strip()})  # 0-indexed
    if project not in PROJECTS:
        print(f"unknown project {project}")
        return 2

    pdf_path = PROJECTS[project]
    out_dir = Path("runs") / f"variant_{variant.lower()}" / project
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Rasterize requested pages only (skip those already on disk)
    todo = [i for i in pages if not (pages_dir / f"page_{i+1:03d}.png").exists()]
    if todo:
        t0 = time.time()
        rasterize(pdf_path, pages_dir, dpi=100, pages=todo)
        print(f"rasterized {len(todo)} pages in {time.time()-t0:.1f}s", flush=True)

    provider = get_provider(model)
    units_path = out_dir / "units.jsonl"
    log_path = out_dir / "run.log"
    cost = 0.0
    new = 0
    t0 = time.time()
    with open(units_path, "a", encoding="utf-8") as fout, \
         open(log_path, "a", encoding="utf-8") as flog:
        for page_idx in pages:
            img = pages_dir / f"page_{page_idx+1:03d}.png"
            t1 = time.time()
            r = provider.extract(img, EXTRACTION_PROMPT)
            cost += r.cost_usd
            elapsed = time.time() - t1
            log_line = {"page": page_idx + 1, "elapsed": round(elapsed, 1),
                        "error": r.error, "raw_len": len(r.raw_text),
                        "in_tok": r.input_tokens, "out_tok": r.output_tokens}
            flog.write(json.dumps(log_line) + "\n")
            if r.error:
                print(f"  p{page_idx+1} ERR: {r.error}", flush=True)
                continue
            page_units = parse_units(r.parsed_json)
            for u in page_units:
                for ev in u.evidence:
                    if ev.page == 0:
                        ev.page = page_idx + 1
                fout.write(json.dumps(u.to_dict()) + "\n")
                new += 1
            print(f"  p{page_idx+1}: +{len(page_units)} units ({elapsed:.1f}s)", flush=True)
    print(f"DONE {variant}/{project}: appended {new} units in {time.time()-t0:.1f}s; cost=${cost:.4f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
