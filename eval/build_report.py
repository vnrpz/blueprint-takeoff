"""Build the deliverable PDF report (TZ §18).

Inputs:
  - runs/leaderboard.csv (or a list of dict rows)
  - 3-4 viewer screenshots (PNG paths)
  - The 4006 metrics row
Outputs:
  - reports/blueprint_takeoff_report.pdf

Sections:
  1. Header — project, date, scope
  2. Winner banner (variant + model + gate pass/fail with explicit gaps)
  3. Eval gate table (TZ §12 thresholds vs actual)
  4. Leaderboard table (sorted)
  5. Synthetic error injection summary (caught / missed / false flags)
  6. Viewer screenshots (3-4)
  7. Limitations + next steps
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional


GATE = {
    "unit_count_error": ("<=", 0.05),
    "group_f1":         (">=", 0.90),
    "qty_mae":          ("<=", 1.0),
    "glass_acc":        (">=", 0.95),
    "egress_acc":       (">=", 0.95),
    "hallucination_rate":("<=", 0.05),
    "error_recall":     (">=", 0.80),
}


def _gate_status(row: Dict, error_recall: Optional[float] = None) -> tuple[bool, List[str]]:
    fails: List[str] = []
    for k, (op, threshold) in GATE.items():
        if k == "error_recall":
            actual = error_recall
        else:
            actual = row.get(k)
        if actual is None:
            fails.append(f"{k}: NO DATA")
            continue
        try:
            actual = float(actual)
        except (TypeError, ValueError):
            fails.append(f"{k}: bad type")
            continue
        if op == "<=" and actual > threshold:
            fails.append(f"{k}={actual:.3f} > {threshold}")
        elif op == ">=" and actual < threshold:
            fails.append(f"{k}={actual:.3f} < {threshold}")
    return (len(fails) == 0, fails)


def build(
    out_path: str | Path,
    leaderboard_csv: str | Path,
    screenshots: List[str | Path],
    error_report: Optional[Dict] = None,
    title: str = "blueprint-takeoff — research report",
) -> Path:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
    )

    rows: List[Dict] = []
    if Path(leaderboard_csv).exists():
        with open(leaderboard_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14, spaceBefore=12, spaceAfter=4)
    body = styles["BodyText"]
    pass_style = ParagraphStyle("pass", parent=styles["BodyText"], textColor=colors.darkgreen, fontName="Helvetica-Bold")
    fail_style = ParagraphStyle("fail", parent=styles["BodyText"], textColor=colors.firebrick, fontName="Helvetica-Bold")

    doc = SimpleDocTemplate(str(out_path), pagesize=LETTER,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    story = []

    story.append(Paragraph(title, h1))
    story.append(Paragraph(
        f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}. "
        f"Repo: <a href='https://github.com/vnrpz/blueprint-takeoff'>vnrpz/blueprint-takeoff</a>.",
        body
    ))
    story.append(Spacer(1, 8))

    # Winner block
    error_recall = (error_report or {}).get("recall")
    rows_4006 = [r for r in rows if r.get("project") == "4006" and r.get("error") in (None, "")]
    rows_4006.sort(key=lambda r: -float(r.get("group_f1") or 0))
    if rows_4006:
        w = rows_4006[0]
        passed, fails = _gate_status(w, error_recall=error_recall)
        status = "GATE PASS ✓" if passed else "GATE FAIL ✗"
        style = pass_style if passed else fail_style
        story.append(Paragraph(f"Winner: Variant {w['variant']} / {w['model']}", h2))
        story.append(Paragraph(status, style))
        if fails:
            story.append(Paragraph("Gaps: " + "; ".join(fails), body))
    else:
        story.append(Paragraph("No 4006 row in leaderboard — no winner.", fail_style))

    # Gate table
    story.append(Paragraph("Eval gate (TZ §12)", h2))
    gate_data = [["Metric", "Operator", "Threshold", "Actual"]]
    actual_row = rows_4006[0] if rows_4006 else {}
    for k, (op, threshold) in GATE.items():
        actual = error_recall if k == "error_recall" else actual_row.get(k, "")
        gate_data.append([k, op, threshold, actual])
    t = Table(gate_data, colWidths=[1.8*inch, 0.7*inch, 1.0*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t)

    # Leaderboard
    story.append(Paragraph("Leaderboard", h2))
    if rows:
        cols = ["variant", "model", "project", "group_f1", "qty_mae", "unit_count_error", "cost_usd"]
        lb_data = [cols] + [[r.get(c, "") for c in cols] for r in rows]
        lb = Table(lb_data, colWidths=[0.55*inch, 1.6*inch, 0.6*inch, 0.7*inch, 0.7*inch, 1.0*inch, 0.7*inch])
        lb.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(lb)
    else:
        story.append(Paragraph("Leaderboard CSV empty.", body))

    # Error injection
    if error_report:
        story.append(Paragraph("Synthetic error injection (TZ §10)", h2))
        caught = error_report.get("caught", [])
        missed = error_report.get("missed", [])
        false_flags = error_report.get("false_flags", [])
        story.append(Paragraph(
            f"Recall: <b>{error_report.get('recall', 0):.2%}</b> &nbsp;|&nbsp; "
            f"Precision: <b>{error_report.get('precision', 0):.2%}</b><br/>"
            f"Caught {len(caught)}; missed {len(missed)}; false flags {len(false_flags)}",
            body
        ))
        if missed:
            story.append(Paragraph(f"Missed: {', '.join(missed)}", fail_style))

    # Screenshots
    if screenshots:
        story.append(Paragraph("Review viewer (bbox overlays)", h2))
        for sp in screenshots:
            if not Path(sp).exists():
                continue
            story.append(KeepTogether([
                Image(str(sp), width=6.5 * inch, height=4 * inch),
                Spacer(1, 6),
                Paragraph(Path(sp).name, body),
            ]))
            story.append(Spacer(1, 12))

    # Limitations
    story.append(PageBreak())
    story.append(Paragraph("Limitations & next steps", h2))
    story.append(Paragraph(
        "Tier-2 facts (hardware, exact RAL color, screens, hand) are not derivable "
        "from the blueprint and are reported as discovery_gaps. The eval gate scores "
        "only Tier-1 fields against ground truth.<br/><br/>"
        "Handwritten scan 1729 — only Variant C (grid tiling) and F (multi-agent on "
        "raster) are realistic carriers. E (vector-first) falls back to B automatically.<br/><br/>"
        "If no pipeline clears the gate, the gap is reported here in numbers — "
        "thresholds are not silently lowered.",
        body
    ))

    doc.build(story)
    return out_path
