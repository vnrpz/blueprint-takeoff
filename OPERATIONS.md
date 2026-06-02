# OPERATIONS — how to run blueprint-takeoff

## Local dev (sandbox-safe)

```bash
pip install -r requirements.txt --break-system-packages
pytest tests/ -v --tb=short            # 31 passed, 37 skipped (real-PDF tests)
```

For Playwright self-QA (review viewer screenshots):

```bash
pip install playwright --break-system-packages
playwright install chromium             # downloads ~280 MB
# On sandboxes that lack chromium-headless-shell:
PLAYWRIGHT_CHROMIUM_EXEC=$HOME/.cache/ms-playwright/chromium-*/chrome-linux64/chrome \
  python scripts/qa_viewer.py --glob 'runs/**/viewer.html'
```

## Full leaderboard run (heavy — use DO droplet per CLAUDE.md)

```bash
export OPENAI_API_KEY=sk-...
export AZURE_OPENAI_ENDPOINT=https://salesdep-openai.openai.azure.com/
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_DEPLOYMENT=gpt-4.1-nano
export GEMINI_API_KEY=AIza...
export TG_BOT_TOKEN=...
export TG_CHAT_ID=...

# Place all six PDFs in data/raw/:
ls data/raw/
#   blueprint.pdf 745_Tamarack_Trail.pdf 321_Sunset.pdf
#   1729_Longvalley.pdf 3122_Lyndale.pdf 4006_N_Sheridan-OFR-0573-2025-2.pdf

python -m eval.run_benchmark \
  --variants A,B,C,D,E,F \
  --models "openai:gpt-4o,openai:gpt-4o-mini,openai:gpt-4.1,azure:gpt-4.1-nano,gemini:gemini-2.5-pro,gemini:gemini-2.5-flash" \
  --projects 4006,745,321,1729,3122 \
  --out-csv runs/leaderboard.csv \
  --out-html runs/leaderboard.html

# Render review viewer for each (variant, project) — TODO wire in
python scripts/qa_viewer.py --glob 'runs/**/viewer.html' --out reports/screenshots

# Build final PDF deliverable
python -c "from eval.build_report import build; build( \
  out_path='reports/blueprint_takeoff_report.pdf', \
  leaderboard_csv='runs/leaderboard.csv', \
  screenshots=sorted(__import__('pathlib').Path('reports/screenshots').glob('*.png')), \
  error_report=None)"
```

## Ingest PDFs from Telegram (background on droplet)

```bash
TG_BOT_TOKEN=... TG_CHAT_ID=... python scripts/poll_tg.py \
  --target-dir data/raw --interval 30
```

```bash
TG_BOT_TOKEN=... TG_CHAT_ID=... python scripts/heartbeat.py \
  --interval 120 --status-file runs/status.json
```

Both scripts are safe to run via `nohup ... &` or `systemd --user`.

## Single-variant single-PDF debug

```bash
python -c "
from src.pipelines import VariantA
from src.vlm import get_provider
p = VariantA(get_provider('openai:gpt-4o'))
r = p.run('data/raw/blueprint.pdf', project='4006')
print(f'units={len(r.units)} cost=${r.cost_usd:.2f} t={r.elapsed_sec:.0f}s')
print(f'errors: {r.errors}')
"
```

## Test gates (CI-friendly)

```bash
# Logic only — no PDFs, no API keys.
pytest tests/test_parsing.py tests/test_matching.py tests/test_metrics.py \
       tests/test_error_injection.py tests/test_eval_gate_4006.py \
       tests/test_neuro_symbolic_injection.py -v

# Pipeline machinery — needs PyMuPDF / OpenCV / Pillow but no API keys.
pytest tests/test_pipeline_smoke.py -v

# Real PDFs + real APIs — gate behind RUN_HEAVY=1.
RUN_HEAVY=1 OPENAI_API_KEY=... pytest tests/test_no_crash_all_projects.py -v
```
