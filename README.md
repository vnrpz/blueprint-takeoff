# blueprint-takeoff

Window / Door Takeoff Engine. Converts construction PDF blueprints into a structured breakdown of every window and door in the project: mark, size, qty, specs (color, profile, glass, U-factor, egress), plus a discrepancy report and an auto-generated list of discovery questions about missing data.

This is a research project. Six pipelines are implemented in parallel, evaluated on a labeled set, the winner is picked by the numbers (eval gate, §12 of TZ).

## Quick start

```bash
pip install -r requirements.txt --break-system-packages
cp .env.example .env  # fill in API keys
pytest tests/ -v --tb=short
python -m eval.run_benchmark  # full leaderboard
```

## Pipelines

| Variant | Strategy |
|---------|----------|
| A | Whole-page VLM baseline |
| B | Semantic region tiling (OpenCV crop + per-region VLM) |
| C | Overlap grid tiling + dedup (SAHI-style) |
| D | Coarse-to-fine pyramid |
| E | Vector-first hybrid (pdfplumber + PyMuPDF, raster fallback to B) |
| F | Multi-agent reconciliation + neuro-symbolic IRC checks |

All pipelines implement `run(pdf_path) -> list[Unit]` with the output schema in `src/schema.py`.

## Layout

```
src/
  schema.py         # Unit dataclass (TZ §4)
  normalize.py      # fraction parsing, spec-group key
  pdf_utils.py      # rasterize, vector detect, page-tools
  credentials.py    # env-based key loader (Bitwarden-friendly)
  vlm/              # provider abstraction (Anthropic / OpenAI / Azure / Gemini)
  pipelines/        # variant_a..f
  viewer/           # review HTML
eval/
  matching.py       # Hungarian bipartite match on spec-groups
  metrics.py        # group_f1, qty_mae, unit_count_error, etc.
  inject_errors.py  # synthetic defect injection (IRC R308.4 / R310 / qty mismatch)
  run_benchmark.py  # leaderboard runner
tests/
  ground_truth/     # 4006.json (golden), 4006_gaps.json, 745.json
  test_*.py
data/raw/           # 6 input PDFs (gitignored, supplied by user)
runs/               # per-pipeline artifacts (gitignored)
reports/            # PDF deliverable
```

## Eval gate (TZ §12) — measured on 4006 N Sheridan

- unit_count_error ≤ 0.05
- group_f1 ≥ 0.90
- qty_mae ≤ 1.0
- glass_acc ≥ 0.95
- egress_acc ≥ 0.95
- hallucination_rate ≤ 0.05
- error_recall ≥ 0.80 (synthetic injection)
- 0 crashes on all 6 PDFs (incl. 1729 handwritten)

If no pipeline passes, the gap is reported explicitly — thresholds are not silently lowered.

## Credentials

Keys are loaded from environment variables (or a local `.env`, gitignored). See `.env.example`. Never committed.

## License

Private — internal tooling.
