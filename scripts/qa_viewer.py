"""Playwright self-QA on the review viewer HTML (TZ §15, §17).

Opens each runs/**/viewer.html under a headless browser, asserts that the
bbox overlay div is present and the units table has at least one row, and
saves a full-page PNG into reports/screenshots/.

Usage:
    pip install playwright --break-system-packages
    python -m playwright install chromium
    python scripts/qa_viewer.py [--glob 'runs/**/viewer.html']

Honors PLAYWRIGHT_CHROMIUM_EXEC env var to bypass the headless_shell lookup.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def screenshot_viewer(html_path: Path, out_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / (html_path.parent.name + "_" + html_path.stem + ".png")
    report = {"html": str(html_path), "png": str(out_png),
              "ok": False, "errors": []}
    exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXEC") or None
    with sync_playwright() as p:
        kwargs = {"headless": True, "args": ["--no-sandbox"]}
        if exec_path:
            kwargs["executable_path"] = exec_path
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(viewport={"width": 1400, "height": 2000})
        page = ctx.new_page()
        page.goto(html_path.absolute().as_uri())
        page.wait_for_load_state("domcontentloaded")
        has_pageframe = page.locator(".pageframe").count() >= 1
        has_units_rows = page.locator("table tbody tr").count() >= 1
        if not has_pageframe:
            report["errors"].append("missing .pageframe")
        if not has_units_rows:
            report["errors"].append("empty units table")
        page.screenshot(path=str(out_png), full_page=True)
        report["ok"] = not report["errors"]
        browser.close()
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="runs/**/viewer.html")
    ap.add_argument("--out", default="reports/screenshots")
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    htmls = sorted(Path(".").glob(args.glob))
    if not htmls:
        print(f"No viewer HTML found under {args.glob}.")
        return 0
    print(f"Found {len(htmls)} viewer file(s).")
    any_fail = False
    for h in htmls:
        rep = screenshot_viewer(h, out_dir)
        status = "OK" if rep["ok"] else "FAIL " + "; ".join(rep["errors"])
        print(f"  {h}  →  {rep['png']}  [{status}]")
        any_fail = any_fail or not rep["ok"]
    return 0 if not any_fail else 2


if __name__ == "__main__":
    sys.exit(main())
