# R5 Decisions

Round date: 2026-06-08

## D1. 4006 is offer-only

**Decision (Option B from R5 brief Task 2).** Drop 4006 from the EXTRACTION
ground-truth map. Keep it for OFFER-side scoring against the manufacturer
schedule.

**Evidence.** R5 v1 `R5_FINDINGS.md §3` ran a PyMuPDF text-extract + schedule
keyword grep across all 144 pages of 4006's `blueprint.pdf`. Only "LIGHT
SCHEDULE" (ceiling fixtures), occupancy, and accessibility tables hit; zero
hits for "window schedule" / "door schedule". `tests/ground_truth/4006_extract.json`
self-flags as "approximate what the R3 gemini sweep observed", i.e. it was
model-derived, not human-transcribed — using it as GT would score a model
against its own past hallucinations.

**Implementation.** `eval/run_benchmark.py`:

```python
GROUND_TRUTH_EXTRACTION = {
    "745":  "tests/ground_truth/745_extract.json",
    "OFR":  "tests/ground_truth/4006_extract.json",  # plumbing smoke only
}
```

OFR row retained as smoke-test plumbing (it's a 12-page offer PDF and the
GT-derivation issue is the same, but it lets the pipeline run end-to-end).

## D2. Variant C parked on rasterized large-format PDFs

**Decision.** On 745 (15-page D-size rasterized), Variant C produced 200–300
1024-px tiles in 12 min and was nowhere near completing. Linear extrapolation
puts the full run at $150–$270 (Claude) or $15–$45 (Gemini) for a *single*
project. Killed both. Recorded in `runs/r5v2_leaderboard.csv` with
`status=killed, error=<reason>`.

**Followup (R6).** Either gate Variant C on `page_is_vector` (skip
rasterized) or change tile defaults (`tile=2048, overlap=0`).

## D3. 745 GT remains "structurally plausible, not transcribed"

**Decision.** Keep `tests/ground_truth/745_extract.json` *as is* for R5 v2.
Do NOT silently edit it to make F1 go up.

**Why.** Editing GT to fit model outputs is exactly the failure mode that
made the R5 v1 leaderboard meaningless. The 745 schedule is on a rasterized
sheet (A1.0) — building a real GT requires VLM-OCR plus human verification.
Surfaced as **R6 work item #1** in `R5_REPORT.md`. Until that is done, all
F1 numbers on 745 are uninterpretable, which is exactly what the R5 v2
report states.

## D4. R5 v2 numbers are computed from on-disk units.jsonl, not the
parallel-run leaderboard.csv

**Decision.** Use the saved per-run `units.jsonl` artifacts as the source of
truth. Re-score them with `eval/metrics.evaluate(pred, gt)` to produce
`runs/r5v2_leaderboard.csv`.

**Why.** Running `eval/run_benchmark.py` four times in parallel (one per
variant×model) caused each invocation to overwrite `runs/leaderboard.csv`
(last writer wins). The per-run units.jsonl files were not affected.

## D5. Bug fix #1 attributed to its real cause

**Decision.** The R5 v1 leaderboard's 8 empty Claude cells were attributed to
"empty units.jsonl (provider returned nothing or invalid JSON each call)".
That label was misleading. The real cause was an HTTP 400 from the Anthropic
API on every call:

```
400 invalid_request_error: `temperature` is deprecated for this model
```

…because `anthropic_provider.py`'s skip-temperature condition was scoped to
`claude-opus-4-8` only, when in fact `claude-opus-4-7` also rejected the
parameter. Fix in `d6c915b`. Documented in `R5_REPORT.md` Fix #1.

