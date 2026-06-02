"""Review viewer (TZ §15).

Renders a one-page HTML per run: left = page image with bbox overlay (color
by kind), right = units table with flags and discovery_gaps. No browser
storage; the JSON payload is inlined.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import List, Optional

from src.schema import Unit


COLORS = {"window": "#1976d2", "door": "#d32f2f", "composite": "#7b1fa2"}


def _img_to_data_uri(p: Path) -> str:
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def render_run(
    project: str,
    variant: str,
    model: str,
    units: List[Unit],
    page_images: List[Path],
    output_html: str | Path,
    metrics: Optional[dict] = None,
) -> Path:
    """Render an HTML review page. Multiple pages can be rendered as
    stacked sections. Returns the output path."""
    units_json = json.dumps([u.to_dict() for u in units], default=str)
    metrics_html = ""
    if metrics:
        items = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in metrics.items())
        metrics_html = f"<details open><summary>Metrics</summary><table class='m'>{items}</table></details>"

    page_blocks = ""
    for p in page_images:
        # bbox overlays: for each unit, emit a transparent div positioned by evidence bbox.
        boxes = []
        for u in units:
            for ev in u.evidence:
                if ev.page == int(p.stem.split("_")[-1]):
                    x, y, w, h = ev.bbox
                    color = COLORS.get(u.kind, "#666")
                    label = f"{u.unit_id} ({u.qty})"
                    boxes.append((x, y, w, h, color, label))
        overlays = "".join(
            f"<div class='box' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;outline:2px solid {c};'>"
            f"<span style='background:{c}'>{lbl}</span></div>"
            for x, y, w, h, c, lbl in boxes
        )
        data_uri = _img_to_data_uri(p)
        page_blocks += f"""
<section><h2>{p.name}</h2>
<div class="pageframe">
  <img src="{data_uri}" alt="{p.name}">
  {overlays}
</div></section>"""

    units_rows = ""
    for u in units:
        flags = ", ".join(u.flags) or "—"
        gaps = ", ".join(u.discovery_gaps) or "—"
        sz = ", ".join(f"{p.width_in:g}×{p.height_in:g}" for p in u.panels)
        units_rows += (
            f"<tr><td>{u.unit_id}</td><td>{u.kind}</td><td>{sz}</td>"
            f"<td>{u.qty}</td><td>{u.confidence:.2f}</td>"
            f"<td class='flags'>{flags}</td><td class='gaps'>{gaps}</td></tr>"
        )

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>blueprint-takeoff — {project} / variant {variant}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;padding:16px;background:#fafafa}}
header{{display:flex;align-items:baseline;gap:24px;border-bottom:1px solid #ccc;padding-bottom:8px;margin-bottom:16px}}
.container{{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:16px}}
section h2{{font-size:14px;color:#555;margin:8px 0}}
.pageframe{{position:relative;display:inline-block;border:1px solid #ddd;background:#fff}}
.pageframe img{{display:block;max-width:100%;height:auto}}
.box{{position:absolute;pointer-events:none}}
.box span{{color:#fff;font-size:11px;padding:1px 4px}}
table{{border-collapse:collapse;width:100%;font-size:13px;background:#fff}}
th,td{{border:1px solid #ddd;padding:4px 6px;text-align:left;vertical-align:top}}
th{{background:#f5f5f5}}
.flags{{color:#c00}}.gaps{{color:#666;font-style:italic}}
details summary{{cursor:pointer;font-weight:600;margin:8px 0}}
table.m th{{width:240px}}
</style></head><body>
<header><h1>blueprint-takeoff</h1>
<div><b>Project</b>: {project}</div><div><b>Variant</b>: {variant}</div><div><b>Model</b>: {model}</div></header>
{metrics_html}
<div class="container">
  <div>{page_blocks}</div>
  <div>
    <h2>Units ({len(units)})</h2>
    <table><thead><tr><th>id</th><th>kind</th><th>size (in)</th><th>qty</th><th>conf</th><th>flags</th><th>discovery_gaps</th></tr></thead>
    <tbody>{units_rows}</tbody></table>
  </div>
</div>
<script type="application/json" id="units_payload">{units_json}</script>
</body></html>
"""
    out = Path(output_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
