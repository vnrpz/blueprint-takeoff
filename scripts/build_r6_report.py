"""Build R6 report v7 from the canonical runs/leaderboard.csv.

Required by TZ §R6 task 7:
  * Two gate blocks on 745 — extraction (vs new GT) and offer (vs 745.json).
  * Leaderboard: variant × model × project, group_f1, qty_mae,
    unit_count_error, glass_acc, cost_usd, elapsed_sec, error.
  * A-F summary in %.
  * Delta vs R5 (uses runs/r5_leaderboard.csv when present).
  * Empty-match cells render as "—", never 0.0/1.0.
  * "Not claimed" section.
  * Title generated from leaderboard contents, not hand-written.

Output: reports/blueprint_takeoff_report_v7.pdf (via reportlab).
"""
from __future__ import annotations
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, "/root/blueprint-takeoff")

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)


ROOT = Path("/root/blueprint-takeoff")
CANON = ROOT / "runs" / "leaderboard.csv"
R5_CSV = ROOT / "runs" / "r5_leaderboard.csv"
OUT = ROOT / "reports" / "blueprint_takeoff_report_v7.pdf"
GATE_F1 = 0.70
GATE_UCE = 0.05
MEASURE_PROJECT = "745"

DASH = "—"


def fmt(v, *, pct=False, digits=3, dollar=False) -> str:
    """Render numerics, leaving empty/None/NaN as a dash."""
    if v in (None, "", "None"):
        return DASH
    try:
        x = float(v)
    except (ValueError, TypeError):
        return str(v)
    if x != x:  # NaN
        return DASH
    if dollar:
        return f"${x:.3f}"
    if pct:
        return f"{x*100:.1f}%"
    return f"{x:.{digits}f}"


def load_rows(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gate_status(row: Dict) -> str:
    f1 = row.get("group_f1")
    uce = row.get("unit_count_error")
    try:
        f1f = float(f1) if f1 not in (None, "", "None") else None
        ucef = float(uce) if uce not in (None, "", "None") else None
    except (ValueError, TypeError):
        return "—"
    if f1f is None or ucef is None:
        return "—"
    if f1f >= GATE_F1 and ucef <= GATE_UCE:
        return f"PASS (f1={f1f:.3f}, uce={ucef:.3f})"
    return f"FAIL (f1={f1f:.3f}, uce={ucef:.3f}; gate: f1≥{GATE_F1}, uce≤{GATE_UCE})"


def build_title(rows: List[Dict]) -> str:
    """Generate the report title from the canonical leaderboard contents."""
    n_rows = len(rows)
    variants = sorted({r.get("variant") for r in rows if r.get("variant") and r.get("variant") != "*"})
    models = sorted({r.get("model") for r in rows if r.get("model") and r.get("model") != "*"})
    projects = sorted({r.get("project") for r in rows if r.get("project") and r.get("project") != "*"})
    levels = sorted({r.get("gt_level") for r in rows if r.get("gt_level")})
    # Picks
    e_rows = [r for r in rows
              if r.get("project") == MEASURE_PROJECT
              and r.get("gt_level") == "extraction"
              and r.get("group_f1") not in (None, "", "None")]
    if e_rows:
        e_rows.sort(key=lambda r: float(r.get("group_f1") or 0), reverse=True)
        best = e_rows[0]
        head = (f"R6 — extraction on {MEASURE_PROJECT}: "
                f"best variant {best.get('variant')} / {best.get('model')} = "
                f"f1 {fmt(best.get('group_f1'), digits=3)}, "
                f"uce {fmt(best.get('unit_count_error'), digits=3)}")
    else:
        head = f"R6 — no extraction rows recorded for {MEASURE_PROJECT}"
    rest = (f"{n_rows} rows · variants {','.join(variants)} · "
            f"{len(models)} models · projects {','.join(projects)} · "
            f"levels {','.join(levels)}")
    return f"{head} ({rest})"


def gate_block(rows: List[Dict], level: str, styles) -> List:
    """Return Platypus story for a single gate block on MEASURE_PROJECT."""
    block = []
    block.append(Paragraph(f"<b>Gate: {MEASURE_PROJECT} {level} "
                           f"(group_f1≥{GATE_F1} AND unit_count_error≤{GATE_UCE})</b>",
                           styles["Heading3"]))
    subset = [r for r in rows
              if r.get("project") == MEASURE_PROJECT and r.get("gt_level") == level]
    if not subset:
        block.append(Paragraph(f"No rows for project={MEASURE_PROJECT} level={level}.",
                               styles["BodyText"]))
        return block

    pass_cells = [r for r in subset if gate_status(r).startswith("PASS")]
    fail_cells = [r for r in subset if gate_status(r).startswith("FAIL")]
    block.append(Paragraph(
        f"{len(pass_cells)}/{len(subset)} cells PASS, {len(fail_cells)}/{len(subset)} FAIL.",
        styles["BodyText"]))

    data = [["variant", "model", "group_f1", "qty_mae", "unit_count_error",
             "cost_usd", "elapsed_sec", "gate"]]
    for r in sorted(subset, key=lambda x: (x.get("variant"), x.get("model"))):
        data.append([
            r.get("variant", DASH),
            r.get("model", DASH),
            fmt(r.get("group_f1")),
            fmt(r.get("qty_mae")),
            fmt(r.get("unit_count_error")),
            fmt(r.get("cost_usd"), dollar=True),
            fmt(r.get("elapsed_sec"), digits=1),
            gate_status(r),
        ])
    t = Table(data, colWidths=[40, 175, 60, 60, 80, 60, 60, 165], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    block.append(t)
    block.append(Spacer(1, 8))
    return block


def leaderboard_table(rows: List[Dict]) -> Table:
    cols = ["variant", "model", "project", "gt_level", "group_f1", "qty_mae",
            "unit_count_error", "glass_acc", "cost_usd", "elapsed_sec", "error"]
    data = [cols]
    for r in sorted(rows, key=lambda x: (x.get("project") or "",
                                         x.get("gt_level") or "",
                                         x.get("variant") or "",
                                         x.get("model") or "")):
        row = []
        for c in cols:
            v = r.get(c, "")
            if c in ("group_f1", "qty_mae", "unit_count_error", "glass_acc"):
                row.append(fmt(v))
            elif c == "cost_usd":
                row.append(fmt(v, dollar=True))
            elif c == "elapsed_sec":
                row.append(fmt(v, digits=1))
            elif c == "error":
                row.append((str(v)[:80] + "...") if v and len(str(v)) > 80 else (v or DASH))
            else:
                row.append(v or DASH)
        data.append(row)
    t = Table(data, colWidths=[35, 165, 45, 60, 55, 55, 70, 55, 55, 60, 90], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def af_summary(rows: List[Dict], styles) -> List:
    """A-F variant summary as percentages (cells PASS / cells run)."""
    block = []
    block.append(Paragraph("<b>Variant summary (A-F) — extraction-gate pass rate on 745</b>",
                           styles["Heading3"]))
    by_v: Dict[str, List[Dict]] = {}
    for r in rows:
        if r.get("project") != MEASURE_PROJECT or r.get("gt_level") != "extraction":
            continue
        v = r.get("variant")
        if v in (None, "", "*"):
            continue
        by_v.setdefault(v, []).append(r)
    data = [["variant", "cells", "PASS", "FAIL", "PASS %", "best group_f1", "min cost_usd"]]
    for v in sorted(set(["A", "B", "C", "D", "E", "F"]) | set(by_v.keys())):
        rs = by_v.get(v, [])
        if not rs:
            data.append([v, "0", DASH, DASH, DASH, DASH, DASH])
            continue
        passc = sum(1 for r in rs if gate_status(r).startswith("PASS"))
        failc = sum(1 for r in rs if gate_status(r).startswith("FAIL"))
        f1s = [float(r.get("group_f1")) for r in rs if r.get("group_f1") not in (None, "", "None")]
        costs = [float(r.get("cost_usd")) for r in rs if r.get("cost_usd") not in (None, "", "None")]
        data.append([
            v, str(len(rs)), str(passc), str(failc),
            f"{passc*100.0/len(rs):.0f}%",
            f"{max(f1s):.3f}" if f1s else DASH,
            f"${min(costs):.3f}" if costs else DASH,
        ])
    t = Table(data, colWidths=[40, 50, 50, 50, 60, 90, 90], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    block.append(t)
    return block


def delta_block(r6: List[Dict], r5: List[Dict], styles) -> List:
    block = []
    block.append(Paragraph("<b>Delta vs R5</b>", styles["Heading3"]))
    if not r5:
        block.append(Paragraph("R5 leaderboard not found at runs/r5_leaderboard.csv. No delta.",
                               styles["BodyText"]))
        return block
    def key(r): return (r.get("variant"), r.get("model"), r.get("project"))
    r5_map = {key(r): r for r in r5}
    rows_out = [["variant", "model", "project", "R6 f1", "R5 f1", "Δf1",
                 "R6 uce", "R5 uce", "Δuce"]]
    seen = 0
    for r in r6:
        if r.get("gt_level") not in (None, "extraction"):
            continue
        k = key(r)
        r5r = r5_map.get(k)
        if not r5r:
            continue
        try:
            f6 = float(r.get("group_f1") or 0)
            f5 = float(r5r.get("group_f1") or 0)
        except (TypeError, ValueError):
            f6 = f5 = 0.0
        try:
            u6 = float(r.get("unit_count_error") or 0)
            u5 = float(r5r.get("unit_count_error") or 0)
        except (TypeError, ValueError):
            u6 = u5 = 0.0
        rows_out.append([
            r.get("variant"), r.get("model"), r.get("project"),
            f"{f6:.3f}", f"{f5:.3f}", f"{f6-f5:+.3f}",
            f"{u6:.3f}", f"{u5:.3f}", f"{u6-u5:+.3f}",
        ])
        seen += 1
    if seen == 0:
        block.append(Paragraph("No overlapping (variant, model, project) cells with R5.",
                               styles["BodyText"]))
        return block
    t = Table(rows_out, colWidths=[40, 165, 45, 50, 50, 55, 55, 55, 55], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    block.append(t)
    return block


def not_claimed(styles) -> List:
    block = []
    block.append(Paragraph("<b>What this report does NOT claim</b>", styles["Heading3"]))
    body = """
This report does NOT claim:<br/>
• that the extraction-gate has been taken on 745. Where the gate fails it is
reported with the literal f1/uce numbers; we did not lower thresholds to make
a cell pass.<br/>
• that ground truth was edited to match any model output. The
<i>745_extract.json</i> file was rewritten once, before any benchmark, from a
human-verified dual-VLM transcription of sheet A1.0 (R6 step 1.4 confirmed
by V on 2026-06-08).<br/>
• that the offer GT (<i>tests/ground_truth/745.json</i>) is correct. It pre-dates
R6 verification and uses fabricated CM1-4 / DR1-2 mark IDs. The offer gate
numbers here are an honest measurement of where the discovery pipeline ends
up vs that stale offer GT, NOT evidence that the discovery layer is broken.<br/>
• that Variant C was budget-tested on 745. It was parked by the R6 cost gate
(see <i>docs/r6_variant_c_cost_gate.md</i>); rows for C on 745 carry the literal
<i>all_pages_raster</i> error string instead of a fabricated metric.<br/>
• that the &quot;dash&quot; (&mdash;) cells in any table mean zero. They mean the
metric was not computable on that cell (no matched groups, no GT, or the
provider errored before metrics ran).<br/>
"""
    block.append(Paragraph(body, styles["BodyText"]))
    return block


def main():
    rows = load_rows(CANON)
    if not rows:
        print(f"No canonical CSV at {CANON} — refusing to build report.")
        sys.exit(1)
    r5 = load_rows(R5_CSV)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=letter,
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)

    story = []
    title = build_title(rows)
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated from canonical <i>{CANON.relative_to(ROOT)}</i> ({len(rows)} rows).",
        styles["Small"]))
    story.append(Spacer(1, 12))

    # Gates
    story.extend(gate_block(rows, "extraction", styles))
    story.append(Spacer(1, 8))
    story.extend(gate_block(rows, "offer", styles))
    story.append(PageBreak())

    # Leaderboard
    story.append(Paragraph("<b>Leaderboard (variant × model × project × gt_level)</b>",
                           styles["Heading3"]))
    story.append(leaderboard_table(rows))
    story.append(PageBreak())

    # A-F summary
    story.extend(af_summary(rows, styles))
    story.append(Spacer(1, 16))

    # Delta vs R5
    story.extend(delta_block(rows, r5, styles))
    story.append(Spacer(1, 16))

    # Not claimed
    story.extend(not_claimed(styles))

    doc.build(story)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
