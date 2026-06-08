# R5 v2 — Honest Benchmark Report

Round date: 2026-06-08
Commit base: `bf8647b` (R5 v1) → `d6c915b` (R5 v2 fixes) → this report.
Run host: `ai-vector-vm` (Azure RG `ai-vector-rg`, polandcentral, IP 20.215.187.179).

---

## TL;DR (numbers are real this time)

| Variant | Model                       | Project | Status  | F1    | Pₜ    | Rₜ    | qty_mae | unit_cnt_err | pred Σqty | cost_usd | elapsed |
|---------|-----------------------------|---------|---------|-------|-------|-------|---------|--------------|-----------|----------|---------|
| A       | anthropic:claude-opus-4-7   | 745     | ok      | 0.062 | 0.038 | 0.167 | 1.00    | 2.29         | 79        | $1.62    | 143 s   |
| A       | gemini:gemini-3.1-pro-preview | 745   | ok      | 0.077 | 0.050 | 0.167 | 2.00    | 1.50         | 60        | (1)      | (1)     |
| E       | anthropic:claude-opus-4-7   | 745     | ok      | 0.000 | 0.000 | 0.000 | —       | 0.92         | 46        | $1.50    | 342 s   |
| E       | gemini:gemini-3.1-pro-preview | 745   | ok      | 0.000 | 0.000 | 0.000 | —       | 1.25         | 54        | (1)      | (1)     |
| C       | anthropic:claude-opus-4-7   | 745     | **killed** | —  | —     | —     | —       | —            | —         | —        | 750+ s  |
| C       | gemini:gemini-3.1-pro-preview | 745   | **killed** | —  | —     | —     | —       | —            | —         | —        | 750+ s  |

(1) Gemini A/E rows are inherited from R5 v1 run (commit bf8647b). The cost/elapsed
fields weren't persisted in that run; we did not re-run Gemini A/E since the
units.jsonl artifacts are intact and re-scoring them under the unchanged metrics
code yields identical numbers.

GT for 745 = 6 unique groups, Σqty = 24 (CM1×4 + CM2×6 + CM3×4 + CM4×4 + DR1×4 + DR2×2).

**Headline:** every variant on 745 is in the noise. Predictions don't share unit_id labels
with the GT, hallucination_rate ≥ 0.95, and matching falls back to (kind × dims × glass)
tuples that don't agree with the GT either. Root cause is not the models — it's that
`745_extract.json` was synthesised from TZ §2 totals + architect-typical RO values
(R5 v1 docs admit this). It is not an OCR transcription of sheet A1.0. Until a real
human-transcribed GT exists for 745, the leaderboard cannot distinguish "model wrong"
from "GT wrong". Documented as R6 work.

---

## What was actually fixed in R5 v2

### Fix #1 — `claude-opus-4-7` HTTP 400 (the *real* reason R5 v1's Claude rows were empty)

`src/vlm/anthropic_provider.py` line 94 (pre-fix):

```python
# claude-opus-4-8 deprecated `temperature`; older opus still accepts it
if not self.model.startswith("claude-opus-4-8"):
    kwargs["temperature"] = 0
```

`claude-opus-4-7` *also* deprecated `temperature` on the Anthropic API. Every
Variant×{A,E,etc.} × Claude call in R5 v1 returned HTTP 400:

```
{'type': 'error', 'error': {'type': 'invalid_request_error',
 'message': '`temperature` is deprecated for this model.'}}
```

`Pipeline.extract` caught the exception, recorded a per-page error, and the loop
moved on — producing the 0-byte `units.jsonl` rows in `r5_leaderboard.csv` that
were labelled "empty units.jsonl (provider returned nothing or invalid JSON each call)"
by `scripts/r5_compile_partial.py`. That label was misleading — the provider returned
*nothing* because it never succeeded; it was *not* "invalid JSON". Fixed condition:

```python
# R5 v2 fix: claude-opus-4-7 and claude-opus-4-8 both reject `temperature`
# (HTTP 400 "deprecated for this model"). Sonnet/Haiku still accept it.
if not (self.model.startswith("claude-opus-4-7") or
        self.model.startswith("claude-opus-4-8")):
    kwargs["temperature"] = 0
```

Verified against `claude-opus-4-7` on `data/raw/745_Tamarack_Trail.pdf` page 1:
`raw_text len = 2486`, `parsed_json` = a 24-mark JSON array (A-X with widths,
heights, glass, qty, egress).

This was the single most consequential bug in R5 v1 — it silently invalidated
every Claude row in the leaderboard.

### Fix #2 — drop 4006 from `GROUND_TRUTH_EXTRACTION`

Per R5 v1 `R5_FINDINGS.md §3`: the 144-page `blueprint.pdf` for project 4006 has
no window/door schedule sheet — only LIGHT SCHEDULE (ceiling fixtures), occupancy
tables, accessibility callouts. `tests/ground_truth/4006_extract.json` admits in
its own `verification_status` that it was "approximate what the R3 gemini sweep
observed on elevations" — i.e. the GT was *model-derived from a previous run*.
Scoring extraction against that file measures a model against its own past
hallucinations.

`eval/run_benchmark.py` updated:

```python
GROUND_TRUTH_EXTRACTION = {
    "745":  "tests/ground_truth/745_extract.json",
    "OFR":  "tests/ground_truth/4006_extract.json",  # plumbing smoke only
}
```

4006 is still in `GROUND_TRUTH_OFFER` (offer-side scoring against the
manufacturer schedule in the offer PDF is honest). The OFR row is kept as a
smoke plumbing test, *not* a real extraction benchmark. This is decision B
from the task brief.

### Fix #3 — `DEFAULT_SHIM_PER_SIDE_IN` (was already correct in `4c41549`)

Was inspected and confirmed already at `0.375` per-side (R5 v1 committed this
in `4c41549`). The associated test was also already updated. No changes
required from R5 v2.

---

## Variant C — runtime/cost decision

`src/pipelines/variant_c.py` tiles every rasterized page at 1024 px with 18 %
overlap, then calls the VLM on each tile. On a 15-page D-size architectural PDF
rasterised at 300 DPI, this produces ~100 tiles per page.

Observed on VM (ai-vector-vm) after 12 minutes:

| Run                                   | Tiles emitted | Pages cracked | Tiles still in flight |
|---------------------------------------|---------------|---------------|------------------------|
| Variant C / claude-opus-4-7 / 745     | 292           | ~3 of 15      | yes                    |
| Variant C / gemini-3.1-pro-preview / 745 | 218        | ~2 of 15      | yes                    |

Linear extrapolation:
- Claude path: ~1500 tiles × $0.10–0.18/call = $150–$270 per project. Far above
  any reasonable single-project budget.
- Gemini path: ~1500 tiles × $0.01–0.03/call = $15–$45. Also above budget for
  a single project comparison.

Variant C has architectural value (small-glyph schedules benefit from tile
zooming) but the current tile parameters (`tile=1024, overlap=0.18`) are not
viable on 15-page D-size projects without a vector-first pre-pass or a much
larger tile size. Decision: **kill, keep the partial PNG tile artifacts** for
R6 cost-analysis, leave a `killed` row in the leaderboard with the reason.

This is not a bug; it's a budget reality. Documented as R6 work: either
(a) gate Variant C on vector-page detection (skip on rasterized) or
(b) raise tile size to 2048 px with 0 overlap.

---

## Methodology / reproduction

All numbers come from the units.jsonl files committed under
`runs/variant_a/745/<model>/units.jsonl` and
`runs/variant_b/745_E_fallback_B/<model>/units.jsonl`. Re-score on any machine
with the repo checked out:

```bash
. .venv/bin/activate
PYTHONPATH=$PWD python - <<'PY'
import json
from pathlib import Path
from src.schema import Unit
from eval.metrics import evaluate
def load_units(p):
    return [Unit.from_dict(json.loads(l)) for l in Path(p).read_text().splitlines() if l.strip()]
gt = [Unit.from_dict(u) for u in json.loads(Path("tests/ground_truth/745_extract.json").read_text())["units"]]
for label, p in [
    ("A_claude", "runs/variant_a/745/claude-opus-4-7/units.jsonl"),
    ("E_claude", "runs/variant_b/745_E_fallback_B/claude-opus-4-7/units.jsonl"),
    ("A_gemini", "runs/variant_a/745/gemini-3.1-pro-preview/units.jsonl"),
    ("E_gemini", "runs/variant_b/745_E_fallback_B/gemini-3.1-pro-preview/units.jsonl"),
]:
    pred = load_units(p); m = evaluate(pred, gt)
    print(label, m.to_dict())
PY
```

The leaderboard CSV is at `runs/r5v2_leaderboard.csv`. Each row carries the
`artifact` path so any number can be traced to the raw model output.

---

## What is *not* claimed in this report

- No claim that any variant×model "wins" on 745. They are all in the noise
  vs. the current `745_extract.json`. R6 needs a hand-transcribed GT from
  sheet A1.0 of the 745 PDF.
- No claim that Variant E with `pdfplumber` extract_tables matters on 745:
  the 745 PDF is fully rasterized (15/15 pages, 0 vector text). Variant E
  immediately falls back to Variant B (region detection + per-region VLM)
  via the existing `if is_vector_any: ...` branch in `variant_e.py`. The
  E rows above are really B-on-detected-regions runs, not pdfplumber-on-vector.
- No claim that 4006 / OFR extraction was re-run in R5 v2. The R5 v1 gemini
  rows for 4006_offer + OFR are inherited unchanged; only the EXTRACTION GT
  map was edited.

---

## Diff summary (R5 v1 → R5 v2)

```
eval/run_benchmark.py         |  8 ++++++--   (drop 4006 from GROUND_TRUTH_EXTRACTION)
src/vlm/anthropic_provider.py |  6 ++++--   (widen temperature-skip to opus-4-7)
runs/r5v2_leaderboard.csv     | NEW         (6 rows, real numbers)
R5_REPORT.md                  | NEW         (this file)
```

## Git log (recent)

```
$ git log --oneline -8
d6c915b R5 v2 fix #1: drop temperature for claude-opus-4-7 (also deprecated)
bf8647b R5 v6 PDF + r5_leaderboard.csv (real numbers, 8/12 cells)
cf9e085 R5 compile: dotenv import is optional (script does no API calls)
15cd5c8 R5: scripts/r5_compile_partial.py — reconstruct leaderboard from on-disk units.jsonl
352024f R5: scripts/build_r5_report.py — generates v6 PDF from r5_leaderboard.csv
d3979c0 R5_FINDINGS.md: PDF audit, project routing, GT decisions
4c41549 R5 fix #1: DEFAULT_SHIM_PER_SIDE_IN = 0.375 (per-side, not total)
3c24b40 R4 batch: GT-extract files, metrics suppression, dual-mode GT, discovery layer, Gemini hardening
```

## Test status

`pytest tests/test_discovery.py` — 5/5 pass (R5 v1 already verified).
No new tests added in R5 v2.

## R6 work surfaced by this round

1. **Hand-transcribe 745 schedule from sheet A1.0** (rasterized — needs a VLM
   plus human verification pass). Replace `745_extract.json` with the real GT.
   Until this is done, the F1 numbers above are uninterpretable.
2. **Variant C cost gate**: skip on rasterized pages, or raise tile to 2048 px
   with overlap=0.
3. **Per-process leaderboard.csv overwrite**: when 4 `run_benchmark.py` instances
   run in parallel, each rewrites `runs/leaderboard.csv` (last writer wins).
   Use a per-run filename or a file lock. R5 v2 worked around this by writing
   `r5v2_leaderboard.csv` directly from the saved units.jsonl artifacts.
4. **Per-kind shim constants** (R5 v1 §2): apply 0 shim at door threshold so
   DR1/DR2 match RO 80.5 → frame 80.0 instead of 79.75.
5. **Variant E vs Variant B naming**: the artifacts of `Variant E → B fallback`
   live under `runs/variant_b/<project>_E_fallback_B/` — this is correct but
   confusing for readers. Either rename the artifact dir or document it more
   prominently.

---

*Signed: R5 v2 batch, ai-vector-vm, 2026-06-08 ~10:50 UTC.*
