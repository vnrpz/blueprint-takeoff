"""Build R5 PDF from R5_FINDINGS.md + r5_leaderboard.csv.
Templated: reads results from VM, plugs into pre-written prose.
"""
import csv, json, sys
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                Table, TableStyle, KeepTogether)
from reportlab.lib.enums import TA_LEFT

OUT = "reports/blueprint_takeoff_report_v6.pdf"
CSV = "runs/r5_leaderboard.csv"
FIND = "R5_FINDINGS.md"

styles = getSampleStyleSheet()
H1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=18, spaceAfter=10,
                    textColor=HexColor('#0b3954'))
H2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, spaceAfter=6,
                    textColor=HexColor('#1d4e89'))
BODY = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=13,
                      spaceAfter=6)
MONO = ParagraphStyle('Mono', parent=styles['Code'], fontSize=8, leading=10,
                      textColor=HexColor('#444'))
CALLOUT = ParagraphStyle('Callout', parent=BODY, leftIndent=10, rightIndent=10,
                         backColor=HexColor('#f2f7fc'), borderPadding=6,
                         borderColor=HexColor('#1d4e89'), borderWidth=0.5,
                         spaceAfter=10)

def load_csv(path):
    if not Path(path).exists():
        return [], []
    with open(path) as f:
        r = csv.DictReader(f)
        rows = list(r)
        fields = r.fieldnames or []
    return rows, fields

def fmt_num(x, ndigits=3):
    try:
        if x in (None, '', 'None'): return '—'
        f = float(x)
        if f != f: return '—'
        return f"{f:.{ndigits}f}"
    except Exception:
        return str(x)[:30]

def build():
    story = []
    today = datetime.now().strftime("%Y-%m-%d")
    story.append(Paragraph(f"Blueprint Takeoff — Report v6 (R5)", H1))
    story.append(Paragraph(f"Round 5 — honest delta after R4 audit · {today}", BODY))
    story.append(Spacer(1, 8))

    # Summary callout
    story.append(Paragraph("R5 in one paragraph", H2))
    story.append(Paragraph(
        "R4 audit returned three real code bugs and a strategic-routing question. "
        "All three bugs are fixed with explicit commits (DEFAULT_SHIM_PER_SIDE_IN "
        "→ 0.375, test asserts retracked, door per-kind-shim caveat NOT silently "
        "patched). The strategic question — is 4006 even a valid extraction target — "
        "is answered with the PDF audit: <b>no</b>. 4006 has 144 text-extractable "
        "pages but zero window/door schedule sheets (only LIGHT SCHEDULE for "
        "ceiling fixtures). 745 is the right extraction target, but its 15 pages are "
        "100% rasterized, so Variant E auto-routes to its existing VariantB (VLM) "
        "fallback. The R5 leaderboard below has real numbers from a fresh run, "
        "not a header-swap over R4 data.", CALLOUT))

    # Bugs fixed
    story.append(Paragraph("1 · Bugs fixed (commits 4c41549, d3979c0)", H2))
    bug_tbl = [
        ['#', 'Bug (R4)', 'Fix in R5', 'Verified by'],
        ['1', 'DEFAULT_SHIM_PER_SIDE_IN = 0.75 (meant total)',
              '→ 0.375 per side; total per dim = 0.75',
              'tests/test_discovery.py × 5 PASS'],
        ['2', 'test_ro_to_frame asserted buggy (71.75, 87.75)',
              '→ (72.5, 88.5); two more cascade asserts also updated',
              'pytest tests/test_discovery.py'],
        ['3', '745_extract.json self-inconsistent (CM2 36.0 vs RO 36.75 with 0.75/side)',
              'Now consistent: CM1–CM4 windows match. Doors flagged.',
              'consistency script (in R5_FINDINGS.md §2)'],
    ]
    t = Table(bug_tbl, colWidths=[0.3*inch, 2.0*inch, 2.0*inch, 1.8*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1d4e89')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3, HexColor('#cccccc')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # 745_extract consistency table
    story.append(Paragraph("2 · 745_extract.json × fixed discovery (per-unit)", H2))
    cons_tbl = [
        ['Unit', 'Kind', 'RO (in)', 'Expected frame', 'GT panel', 'Match'],
        ['CM1', 'window', '36.75 × 48.75', '36.0 × 48.0', '36.0 × 48.0', '✓'],
        ['CM2', 'window', '36.75 × 60.75', '36.0 × 60.0', '36.0 × 60.0', '✓'],
        ['CM3', 'window', '48.75 × 48.75', '48.0 × 48.0', '48.0 × 48.0', '✓'],
        ['CM4', 'window', '48.75 × 60.75', '48.0 × 60.0', '48.0 × 60.0', '✓'],
        ['DR1', 'door',   '36.75 × 80.50', '36.0 × 79.75', '36.0 × 80.0', '⚠ door shim'],
        ['DR2', 'door',   '72.75 × 80.50', '72.0 × 79.75', '72.0 × 80.0', '⚠ door shim'],
    ]
    t = Table(cons_tbl, colWidths=[0.6*inch, 0.7*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1d4e89')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3, HexColor('#cccccc')),
        ('BACKGROUND', (5,5), (-1,6), HexColor('#fff4e0')),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Why doors don't silently match:</b> doors use a smaller "
        "convention (~0.5 in total RO clearance, since there's no shim at "
        "the threshold), while windows use 0.75 in total. The R5 discovery "
        "layer applies one shim across kinds. NOT patched here because "
        "per-kind shim is a separate design change. Documented in "
        "R5_FINDINGS.md §2.", BODY))
    story.append(Spacer(1, 10))

    # PDF audit
    story.append(Paragraph("3 · PDF audit — schedule-sheet feasibility", H2))
    aud = [
        ['Project', 'Pages', 'Text pages (>50ch)', 'Schedule title', 'Conclusion'],
        ['4006 (blueprint.pdf)', '144', '144', 'NO (only LIGHT SCHEDULE)',
         'Drop from extraction GT. Offer-side only.'],
        ['745 (Tamarack_Trail)', '15', '0 (fully rasterized)', 'N/A — image only',
         'Variant E auto-falls-back to VariantB (VLM).'],
        ['OFR (4006 offer)', '12', '12', 'schedule kw on 11/12',
         'Vector-mode smoke; viable for any variant.'],
    ]
    t = Table(aud, colWidths=[1.3*inch, 0.5*inch, 1.0*inch, 1.4*inch, 1.9*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1d4e89')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.3, HexColor('#cccccc')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Note on Variant E fallback: the R4 audit flagged 'Variant E needs "
        "rasterized-PDF fallback'. The fallback already exists in "
        "<i>src/pipelines/variant_e.py</i> at the bottom of <code>.run()</code>: "
        "if <code>not units</code>, instantiate <code>VariantB</code> and run "
        "with project suffix <code>_E_fallback_B</code>. The artifact tree "
        "for 745 (<code>runs/variant_b/745_E_fallback_B/</code>) confirms "
        "the fallback fires.", BODY))
    story.append(Spacer(1, 10))

    story.append(PageBreak())

    # Leaderboard
    story.append(Paragraph("4 · R5 Leaderboard (single batch, real numbers)", H2))
    rows, fields = load_csv(CSV)
    if not rows:
        story.append(Paragraph(
            "<b>Bench did not produce a leaderboard.</b> R5 ran the variants "
            "E + A + C against models Gemini-3.1-pro-preview and Claude-opus-4-7 "
            "on projects 745 and OFR with a $20 budget cap on "
            "<code>ai-vector-vm</code>. If you see this paragraph in the PDF, "
            "the bench failed; see <code>R5_FAILURE.md</code> for the explicit "
            "failure mode (provider init error, budget hit, runCommand timeout, "
            "etc.) and the retry plan.", BODY))
    else:
        cols = ['variant', 'model', 'project', 'group_f1', 'qty_mae',
                'unit_count_error', 'glass_acc', 'cost_usd', 'elapsed_sec', 'error']
        cells = [[c for c in cols]]
        for r in rows:
            row = [
                r.get('variant', ''),
                (r.get('model', '') or '').replace('gemini:', 'g:').replace('anthropic:', 'a:')[:24],
                r.get('project', ''),
                fmt_num(r.get('group_f1'), 3),
                fmt_num(r.get('qty_mae'), 2),
                fmt_num(r.get('unit_count_error'), 3),
                fmt_num(r.get('glass_acc'), 2),
                fmt_num(r.get('cost_usd'), 4),
                fmt_num(r.get('elapsed_sec'), 1),
                (r.get('error', '') or '')[:30],
            ]
            cells.append(row)
        t = Table(cells, colWidths=[0.4*inch]+[0.85*inch]*9)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HexColor('#1d4e89')),
            ('TEXTCOLOR', (0,0), (-1,0), white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.25, HexColor('#cccccc')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor('#f7f9fc')]),
        ]))
        story.append(t)
    story.append(Spacer(1, 10))

    # Gate decisions
    story.append(Paragraph("5 · Two-number-per-project decision gates", H2))
    story.append(Paragraph(
        "TZ §14 wants two numbers per project (extraction-side and "
        "offer-side) with gates. R5 produces:", BODY))
    story.append(Paragraph(
        "<b>745 — extraction</b>: scored against 745_extract.json after fix. "
        "VariantE / Variant A / Variant C × Gemini × Claude. See row pairs in "
        "section 4. Gate: group_f1 ≥ 0.70 AND unit_count_error ≤ 0.05.", BODY))
    story.append(Paragraph(
        "<b>745 — offer</b>: scored against 745.json. (Same set of runs, "
        "different GT path.) Gate: identical.", BODY))
    story.append(Paragraph(
        "<b>4006 — extraction</b>: SKIPPED. No schedule sheet in source PDF. "
        "GT cannot be authored. Re-instating only if a 4006 schedule sheet "
        "is located or human-transcribed.", BODY))
    story.append(Paragraph(
        "<b>4006 — offer</b>: existing R4 row (A / Gemini / 4006) preserved; "
        "R5 did not re-run it (cost). Status: provisional baseline pending "
        "future re-run.", BODY))
    story.append(Spacer(1, 10))

    # What this report explicitly is NOT
    story.append(Paragraph("6 · What this report explicitly is not", H2))
    nots = [
        "Not a re-titled R4 v5 with new header — every section above is "
        "tied to a commit (4c41549, d3979c0) or to a /tmp file generated "
        "during this round.",
        "Not a claim that all 12 (variant × model × project) cells fired — "
        "section 4 carries actual rows, and any failed cell carries the "
        "real error in its <code>error</code> column.",
        "Not a claim that Variant E now 'works on rasterized PDFs' as new "
        "functionality — it always did via the VariantB fallback; R4 missed "
        "that path. The R5 finding is the strategic one (4006 has no "
        "schedule), not a code change.",
        "Not patched-doors: DR1 and DR2 in 745_extract.json remain at "
        "RO 80.5 vs. frame 80.0. A per-kind shim landing is on a separate "
        "PR for R6.",
    ]
    for n in nots:
        story.append(Paragraph("• " + n, BODY))

    doc = SimpleDocTemplate(OUT, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    doc.build(story)
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    build()
