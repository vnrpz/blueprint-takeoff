# Definition of Done

Per TZ §17. A green tick means automated, not manual.

## Code

- [x] All 6 variants implement `Pipeline.run(pdf_path) -> PipelineRun` with the same `Unit` schema. (registry: `src.pipelines.VARIANTS`)
- [x] VLM providers behind one interface (`src.vlm.base.VLMProvider`) — OpenAI / Azure-OpenAI / Gemini + MockProvider (+ Anthropic file kept but out of leaderboard scope per user).
- [x] Normalization is testable in isolation — fractions, mirror folding, spec-group key.
- [x] Matching is Hungarian on spec-groups with τ=1.0 in and field-conflict gating.
- [x] All metrics from TZ §9 implemented in `eval/metrics.py` with formulas reproducible against the 4006 self-eval.
- [x] Synthetic error injection (10 defect variants) in `eval/inject_errors.py`.
- [x] Leaderboard runner emits CSV + HTML, winner selection per TZ §14.
- [x] Review viewer HTML (bbox overlay + units table + flags + discovery_gaps), no browser storage.
- [x] PDF report builder (`eval/build_report.py`) with winner, gate, leaderboard, error injection, screenshots, limitations.
- [x] Playwright self-QA script (`scripts/qa_viewer.py`) producing screenshots for the report.
- [x] TG ingest (`scripts/poll_tg.py`) + heartbeat (`scripts/heartbeat.py`).

## Tests

- [x] `pytest tests/ -v --tb=short` — 66 passed, 43 skipped (skipped = real-PDF / heavy tests). Green on a clean checkout (no PDFs, no keys); enforced by CI (`.github/workflows/ci.yml`).
- [x] `tests/test_parsing.py`, `tests/test_matching.py`, `tests/test_metrics.py` cover the pure logic.
- [x] `tests/test_credentials.py` — `_Secret` masks its value in repr and never leaks into log output.
- [x] `tests/test_branch1_ofr.py` — branch-1 parsing/normalization + `to_schema` covered on synthetic input (real-PDF e2e skips when the gitignored offer PDF is absent).
- [x] `tests/test_error_injection.py` proves the oracle-detector path hits recall=1.0 and the silent-detector path hits 0.0 — gate is meaningful.
- [x] `tests/test_eval_gate_4006.py` proves the gate passes on perfect predictions and fails on corrupted predictions.
- [x] `tests/test_pipeline_smoke.py` exercises all 6 variants end-to-end on a synthetic PDF with MockProvider — no crashes, every output round-trips through `Unit.from_dict`.
- [ ] `tests/test_no_crash_all_projects.py` parametrised across (variant × project) — currently skipped (PDFs absent); flip with `RUN_HEAVY=1`.
- [ ] `tests/test_eval_gate_4006.py::test_winning_pipeline_meets_gate` — pending real leaderboard run.

## Data

- [x] `tests/ground_truth/4006.json` — TZ §3 hardcoded, total = 230 ✓.
- [x] `tests/ground_truth/4006_gaps.json` — Tier-2 discovery list.
- [ ] `tests/ground_truth/745.json` — stub awaiting `745_Tamarack_Trail.pdf`.

## Process

- [x] `PLAN.md` checked in.
- [x] `SECURITY_CHECKLIST.md` checked in.
- [x] `DEFINITION_OF_DONE.md` (this file).
- [x] CI wired (`.github/workflows/ci.yml`): runs the full suite on push/PR across Python 3.10–3.12 and asserts every first-party module imports without a PDF, key, or network.
- [ ] Eval gate prog run on 4006, leaderboard rendered, winner declared. (BLOCKED on PDFs + DO droplet.)
- [ ] PDF report `reports/blueprint_takeoff_report.pdf` produced from real run.
- [ ] Delivery posted to TG @vtlik with: winner, key 4006 metrics, gate pass/fail, viewer screenshots, leaderboard link, error injection summary.
