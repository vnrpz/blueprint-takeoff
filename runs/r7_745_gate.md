# R7 — 745 raster-table gate (Задача 4)

Method: render sheet A1.0 (page 1, raster) at 300 DPI -> VLM reads the Window/Door
Schedule table into strict JSON rows -> deterministic notation decoder (src/notation.py,
Weather Shield) -> qty from the QTY column -> evaluate() vs human-verified 745_extract.json.

This fixes R6 root cause: variant_c SKIPPED raster pages (cost gate), so 745's schedule
was never read (f1=0.091). R7 renders+reads that sheet directly.

## Result (claude-opus-4-8, single reader; cost $0.098)
- rows read: 8 / decoded units: 8 / pred total qty: 24 (GT total: 24)
- **group_f1 = 0.875**  (gate >= 0.70 — TAKEN)
- **unit_count_error = 0.000**  (gate <= 0.05 — TAKEN)
- precision 0.875 / recall 0.875 / matched 7 / fp 1 / fn 1
- **GATE TAKEN**

Note: dual-VLM cross-check (TZ) not run this pass — Gemini key is free-tier
(quota 0 for gemini-3.1-pro), OpenAI key returned 401. Billed Anthropic Opus-4-8
used as single reader. Result is honest literal numbers, thresholds not adjusted.
