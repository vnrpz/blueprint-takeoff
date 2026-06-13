# SECURITY_CHECKLIST

Per TZ §17 QA protocol. Re-run before any release.

## Input validation

- [x] PDFs opened with `PyMuPDF.open(strict=True)` (default in `pdf_utils.open_pdf`); malformed files fail fast rather than silently degrade.
- [x] Hard size limit: reject any PDF over 50 MB before rasterization (rasterizing a 500 MB hand-scan would crash the sandbox).
- [x] Password-protected PDFs explicitly rejected unless a key is supplied.
- [x] No `eval()` / `exec()` on extracted JSON; every parse uses `json.loads` + tolerant pydantic-style validation in `src/pipelines/parsing.py`.
- [x] Spec-group keys are typed tuples; matching uses `scipy.optimize.linear_sum_assignment` — no string-eval surface.

## Credential handling

- [x] `src/credentials.py` reads keys from environment + optional `bw` CLI; default `.env` is gitignored.
- [x] `_Secret(str)` masks the value in `__repr__` so accidental `print(creds)` never leaks.
- [x] Tests assert no key string appears in `caplog` output (`tests/test_credentials.py`, run by CI in `.github/workflows/ci.yml`).
- [x] No credentials ever written into `runs/` or `reports/`.

## File system

- [x] All writes are confined to `runs/<variant>/<project>/` and `reports/`.
- [x] No user-supplied path is concatenated into output dirs — only stems derived from PDF filename, with `Path` semantics so traversal is blocked.
- [x] `runs/` and `reports/*.pdf` are gitignored to keep accidental artifacts out of the repo.

## VLM provider safety

- [x] Mocked tests cover normalize/match/metrics with `MockProvider` — CI never calls real APIs without a `RUN_HEAVY=1` opt-in.
- [x] No image payload contains the user's environment beyond the page crop.
- [x] Each provider implements its own retry; nothing silently swallows quota errors.

## Reporting

- [x] PDF report lists only Tier-1 facts from the chart; Tier-2 facts are explicitly labeled `discovery_gaps`.
- [x] If the eval gate fails, the gap (which thresholds were not met and by how much) is shown in the report. The gate is NEVER quietly lowered.

## Out-of-scope

- Cloud IAM / VPC config — runs are deliberately stateless, no production network access required.
