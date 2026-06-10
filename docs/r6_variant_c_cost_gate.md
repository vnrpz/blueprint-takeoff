# Variant C cost gate (R6)

## Problem (R5 observation)

Variant C is SAHI-style overlap tiling. The R5 defaults (`tile=1024`,
`overlap=0.18`) produced **200–300 tiles per raster page** on the
`745_Tamarack_Trail.pdf` set (15 pages, ~10800×7200 each at 300 DPI). At
Claude/Gemini per-tile prices that translates to roughly **$150–270 of
Claude or $15–45 of Gemini** for a single project. R5 hit the per-run
budget cap with no usable extraction (the tiles are crops of a blurry
scan; nothing useful comes out).

## Decision (one of the two TZ §R6 options)

We took **option (a): gate Variant C by `page_is_vector` and skip raster
pages**, with a secondary tightening on the tile defaults.

* `src/pipelines/variant_c.py`:
  * Skip pages where `page_is_vector == False`. Record them in
    `PipelineRun.errors` so the leaderboard row carries a `skipped_reason`
    and does not silently appear as an empty cell.
  * Lowered tile count for the remaining (vector) pages by changing the
    defaults to `tile=2048, overlap=0`. On a typical vector sheet this
    drops tiles from O(150) to O(20).
  * If **every** page is raster, the run emits
    `all_pages_raster: Variant C not applicable` and produces zero units
    at zero cost.

## Effect on R6 leaderboard

* `745` (15 raster pages, including A1.0): Variant C will produce a
  row with `error="all_pages_raster: ..."` and cost_usd=0. The R6 report
  v7 must surface this row as parked-with-reason, not silently dropped.
* `4006` (vector PDF, offer-only): Variant C is unaffected by the
  raster gate; the budget impact comes only from the lowered tile count.

## Reproducing the budget hit

If we ever want to re-enable raster tiling for Variant C (e.g. for a
high-DPI Gemini run with a strict budget), pass the legacy parameters
directly via env or refactor `DEFAULT_TILE_PX`/`DEFAULT_OVERLAP`. We did
not turn the legacy path into a CLI flag — it should require a code
change to opt back in.
