# PLAN.md — blueprint-takeoff

Per QA protocol §17: brainstorm → PLAN → checkpoint → TDD → autotests → neuro-symbolic checks → Playwright MCP self-QA → SECURITY_CHECKLIST → eval gate → DoD → PDF report → Telegram.

## Architecture decisions

1. **Output schema is single source of truth.** Every pipeline returns `list[Unit]` per `src/schema.py`. Matching/metrics/viewer/report all consume that shape.
2. **VLM provider is abstracted.** `src/vlm/base.py` defines `extract(image, prompt, schema_hint=None) -> dict`. Concrete classes for Anthropic, OpenAI, Azure-OpenAI, Gemini. Each variant can be re-run across 2-3 models — that comparison powers the leaderboard.
3. **Normalization happens BEFORE matching.** `src/normalize.py` parses fractions (`72 1/2` → 72.5, `36 3/16` → 36.1875), builds the spec-group key `(kind, round(w), round(h), glass, ufactor_bucket, egress)`, folds mirror pairs (left/right) since per TZ §3 those are Tier-2.
4. **Matching is Hungarian (max-weight bipartite).** `scipy.optimize.linear_sum_assignment`. Edge weight = 1 / (1 + size_distance_in) inside same kind, with tau=1.0in tolerance gate.
5. **Neuro-symbolic layer is geometric, not VLM.** After detection, `eval/inject_errors.py`-shaped checks run algorithmically: window-to-door distance (IRC R308.4 tempered), sill height (R308.4 + R310 egress), clear opening sqft (R310). Flags are added to `Unit.flags`.
6. **Synthetic error injection is the main correctness signal.** Real labels are scarce (we only fully label 4006 + 745). Injection generates known defects → measures `error_recall`/`error_precision` without manual re-labeling.
7. **Determinism for tests.** Variant A on a 1-page synthetic PDF must give a stable output regardless of model temperature — the test mocks the VLM provider and asserts the parsing/matching/metrics pipeline.
8. **No browser storage.** Review viewer is pure HTML + inline JSON, all in-memory.

## Stage map (this iteration)

| # | Stage | Blocking |
|---|------|----------|
| 0 | Repo skeleton, credentials loader, gitignore, layout | — |
| 1 | Acquire 6 PDFs (TG ask sent) | user response |
| 2 | Ground truth: 4006 from TZ §3 hardcoded; 4006_gaps; 745 stub | none |
| 3 | Schema + normalization + tests | none |
| 4 | VLM provider abstraction + 4 implementations | API keys ok |
| 5 | Variant A baseline | 4, PDFs |
| 6 | Matching + metrics + tests | 3 |
| 7 | Synthetic error injection | 3, 6 |
| 8 | Variants B-F | 5, 6 |
| 9 | Leaderboard runner | 8 |
| 10 | Review viewer HTML | 8 |
| 11 | pytest suite green + Playwright self-QA | 9, 10 |
| 12 | PDF report + TG delivery | 11 |

## Known unknowns

- Anthropic API key not in memory. Will request from user if Variant A needs Claude.
- 745 Tamarack ground truth has to be hand-built from the Window Schedule on sheet A1.0 — requires the PDF first.
- IRC bedroom detection (for R310 egress flag) needs room labels from plan views — Variant F responsibility, may not survive on rasterized handwritten 1729.

## Security checklist (TZ §17)

- PDF size limit: 50 MB per file, hard cap before rasterization.
- Input validation: `PyMuPDF.open(strict=True)`; reject if password-protected unless flag set.
- No credentials in logs: `credentials.py` masks the value in `__repr__`. Tests assert no key string in `caplog`.
- No `eval()` / `exec()` on extracted JSON; strict `json.loads` + pydantic parse.
- All file writes go to `runs/<variant>/<project>/` — no traversal.
