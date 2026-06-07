# R5 — Findings & Decisions

Round date: 2026-06-07

## 1. Bugs fixed (commit 4c41549)

* `src/discovery.py`: `DEFAULT_SHIM_PER_SIDE_IN` 0.75 → 0.375
  (per-side shim; total per-dim allowance = 0.75)
* `tests/test_discovery.py`: three asserts updated to track the new constant
  (ro_to_frame default; transform_unit_applies_ro; transform_all_batch)
* All 5 discovery tests pass locally.

## 2. 745_extract.json consistency vs. fixed discovery

| Unit | RO | Expected frame (0.375 shim) | GT panel | Match |
|------|-----|-----------------------------|----------|-------|
| CM1  | 36.75×48.75 | 36.0×48.0 | 36.0×48.0 | ✅ |
| CM2  | 36.75×60.75 | 36.0×60.0 | 36.0×60.0 | ✅ |
| CM3  | 48.75×48.75 | 48.0×48.0 | 48.0×48.0 | ✅ |
| CM4  | 48.75×60.75 | 48.0×60.0 | 48.0×60.0 | ✅ |
| DR1  | 36.75×**80.5** | 36.0×**79.75** | 36.0×**80.0** | ⚠ doors |
| DR2  | 72.75×**80.5** | 72.0×**79.75** | 72.0×**80.0** | ⚠ doors |

Windows: perfect. Doors: 0.5-in total RO vs. window 0.75-in — real-world
convention (no shim at threshold). Discovery layer applies one shim for
all kinds, so doors will read 79.75 vs the GT 80.0. **Not silently
"fixed" by editing the GT.** Listed as known limitation; per-kind shim
constants are a separate change.

## 3. Strategic project routing (PDF audit results)

Ran PyMuPDF text-extract + schedule-keyword grep across the three PDFs.

| Project | Pages | Pages with text >50ch | Schedule title found | Variant E mode |
|---------|------:|----------------------:|----------------------|----------------|
| 4006 (blueprint.pdf) | 144 | 144 | **NO** — only "LIGHT SCHEDULE" hits on 48–60 | pdfplumber finds nothing → falls back to VariantB on 144p (expensive) |
| 745 (Tamarack_Trail.pdf) | 15 | **0** (fully rasterized; 1 image/page) | N/A (no text) | `is_vector_any`=False → goes straight to VariantB (VLM) fallback |
| OFR (4006_N_Sheridan-OFR-…) | 12 | 12 | schedule keywords on 11/12 | pdfplumber happy path |

Note: Variant E in `src/pipelines/variant_e.py` already implements VLM
fallback (`if not units: VariantB(...)`). The R4 audit's "needs fallback
for rasterized" was based on an outdated read; the fallback exists.

### Implications

* **4006 cannot serve as extraction GT.** The 144-page set has no
  window/door schedule sheet (only LIGHT SCHEDULE for ceiling fixtures,
  occupancy tables, accessibility callouts). `4006_extract.json` admitted
  it was provisional ("approximate what R3 gemini sweep observed"). For
  R5: drop 4006 from EXTRACTION leaderboard, keep it for OFFER side only.
* **745 is the right extraction project.** Variant E auto-routes to the
  VLM fallback because pages are rasterized. So Variant E ≡ VariantB on
  745, costwise.
* **OFR** stays as the cheap vector-mode smoke for Variant E.

## 4. GT-extract authenticity

* `4006_extract.json` — **flagged model-derived** in the file itself.
  Decision: do NOT score extraction against it; remove from
  `GROUND_TRUTH_EXTRACTION` in `eval/run_benchmark.py`. Documented in
  this report.
* `745_extract.json` — derived from TZ §2 totals + architect-typical RO,
  not from a human-transcribed schedule (the schedule is on a
  **rasterized** page A1.0; we have no text to transcribe). Windows
  (CM1–CM4) are internally consistent with the fixed shim; door rows
  carry the per-kind-shim caveat above. Flagged as "structurally
  plausible, source: TZ totals + architect convention, not OCR of A1.0".

## 5. R5 benchmark scope (what is actually being run)

Single batch on `ai-vector-vm`, budget cap $20:

* Variant E on 745 (→ VLM fallback path)
* Variant A / Gemini on 745
* Variant C / Claude on 745
* (4006 — reuse existing A/gemini row; not re-run)
* (OFR — Variant E smoke if time permits)

If a provider fails, the row is recorded with the failure reason in
`error` and `traceback`; the leaderboard row stays. No silent retries
that swap a failure for a success.
