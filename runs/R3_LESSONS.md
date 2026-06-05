# Round 3 lessons — for next iteration

Saved here so future runs don't repeat the same mistakes.

## Compute target

- **DO PATs are stale across 2 rotations.** Don't rely on memory snapshots.
  Use BW lookup each session.
- **Azure SP runCommand on `ai-vector-vm` (RG `AI-VECTOR-RG`, polandcentral)** is
  the working compute path. Token expires every 60 min — refresh between long runs.
- The user's `.claude/CLAUDE.md` rule "Never run heavy ops in Coworker sandbox"
  still holds. 300 DPI rasterization of D-size sheets is heavy: ~3.6 GB per
  144-page PDF, ~10-30 min wall clock per project/model pair.

## Anthropic vision API quirks (BW item 3fb46199 / a0f11130)

1. **Hard image-dim cap = 8000 px** on any side. Resize before sending.
   `src/vlm/anthropic_provider.py` uses Pillow Lanczos to 7680 px longest.
2. **`temperature` deprecated on `claude-opus-4-8`** (still accepted on 4-7
   and earlier). The provider checks `self.model.startswith("claude-opus-4-8")`
   and omits the param.
3. Default model now `claude-opus-4-8` (newest in `/v1/models` probe).

## PyMuPDF rasterize quirk (BW item 6f0f9d02)

PyMuPDF returns the **native resolution** of any embedded raster regardless
of the zoom matrix you pass. Even at `dpi=100` a D-size scanned PDF page
can yield a 10800 × 7200 PNG. If you need a hard pixel cap, downscale with
Pillow after `rasterize()` returns.

## Gemini timeouts on D-size sheets

`gemini-3.1-pro-preview` returns `DeadlineExceeded 504` on 300 DPI D-size
pages with default SDK timeout (~120 s). Recommended: retry with backoff
**and** pre-resize to ≤ 5000 px longest side before submission.

## Scoring policy

Per TZ §19 #2: **score blueprint.pdf direct against `tests/ground_truth/4006.json`**.
Don't use the OFR offer as a proxy "winner" — it has the canonical schedule
because it IS the offer that produced the GT. Treat OFR as a plumbing smoke
test for the pipeline machinery; the real eval is on the building's drawing set.

## spec_group_key relaxation (R3)

The strict (kind, role, w, h, glass, u, egress) key was driving
hallucination_rate to 1.0 when a model classified glass as `null` instead
of `mixed`. Relaxed to (kind, role, w, h); glass/u/egress are now scored
as field accuracy on the matched subset. See `src/normalize.py` and
`eval/matching.py`.

## Ceiling pattern — Variant E is the answer

R1, R2, R3 all hit the same ceiling on 4006: VLMs read **elevation views**
(visible W1, W2 marks on building facades) and report drawing-frame
dimensions like 36×60 — NOT the schedule canonical 72.5×88.5×qty=63.

The schedule sheet **is in the PDF set but the text is a table**, not a
visual. **`Variant E` (pdfplumber tables → structured rows)** is the
right tool for this. Then Variant F reconciles E with elevation counts
to confirm qty.

For R4: prioritise Variant E + F. Skip Variants A/B/C/D on 4006/blueprint.pdf
(the elevation drawings won't give you the schedule data).
