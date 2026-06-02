"""Variant E step runner — pdfplumber tables, per-page state. No VLM."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pdfplumber

from src.normalize import parse_inches
from src.schema import Unit, Panel

PROJECTS = {
    "4006":  "data/raw/blueprint.pdf",
    "745":   "data/raw/745_Tamarack_Trail.pdf",
    "321":   "data/raw/321_Sunset.pdf",
    "1729":  "data/raw/1729_Longvalley.pdf",
    "3122":  "data/raw/3122_Lyndale.pdf",
    "OFR":   "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf",
}

SCHEDULE_HEADERS = {"mark", "size", "width", "height", "type", "glass", "u-factor",
                    "u factor", "ufactor", "egress", "qty", "quantity"}


def _try_parse(s):
    try: return parse_inches(s)
    except Exception: return None


def process_page(pdf, pi: int, out: list):
    page = pdf.pages[pi]
    tables = page.extract_tables() or []
    found = 0
    for t in tables:
        if not t or not t[0]:
            continue
        header = [str(c or "").strip().lower() for c in t[0]]
        hits = sum(1 for h in header if h in SCHEDULE_HEADERS)
        if hits < 2:
            continue
        cols = {h: i for i, h in enumerate(header)}
        for row in t[1:]:
            row = [str(c or "").strip() for c in row]
            try:
                mark_idx = cols.get("mark") or 0
                mark = row[mark_idx] or f"R{pi}-{len(out)}"
                # Size: try several columns
                width = height = None
                if "size" in cols:
                    s = row[cols["size"]]
                    if "x" in s.lower():
                        wstr, _, hstr = s.lower().partition("x")
                        width = _try_parse(wstr)
                        height = _try_parse(hstr)
                if width is None and "width" in cols:
                    width = _try_parse(row[cols["width"]])
                if height is None and "height" in cols:
                    height = _try_parse(row[cols["height"]])
                if width is None or height is None:
                    continue
                glass_raw = row[cols["glass"]].lower() if "glass" in cols and row[cols["glass"]] else ""
                glass = ("tempered" if "temp" in glass_raw else
                         "annealed" if "ann" in glass_raw else
                         "mixed" if "mix" in glass_raw else None)
                u_factor = None
                for h in ("u-factor", "u factor", "ufactor"):
                    if h in cols and row[cols[h]]:
                        try: u_factor = float(row[cols[h]].split()[0]); break
                        except: pass
                egress = None
                if "egress" in cols:
                    s = row[cols["egress"]].lower()
                    if s in ("y", "yes", "true", "x"): egress = True
                    elif s in ("n", "no", "false", "-"): egress = False
                qty = 1
                for q in ("qty", "quantity"):
                    if q in cols and row[cols[q]]:
                        try: qty = int(row[cols[q]]); break
                        except: pass
                kind = "door" if mark.upper().startswith("D") else "window"
                unit = Unit(
                    unit_id=mark, kind=kind, qty=qty,
                    panels=[Panel(role=kind, width_in=width, height_in=height,
                                  glass=glass, u_factor=u_factor, egress=egress)],
                    source_marks=[mark], confidence=0.95,
                )
                out.append(unit)
                found += 1
            except Exception:
                continue
    return found


def main(argv) -> int:
    if len(argv) < 3:
        print("usage: step_runner_e.py <project> <page_csv|all>")
        return 2
    project = argv[1]
    pages_arg = argv[2]
    if project not in PROJECTS:
        print(f"unknown project: {project}"); return 2
    pdf_path = PROJECTS[project]
    out_dir = Path("runs") / "variant_e" / project
    out_dir.mkdir(parents=True, exist_ok=True)
    units_path = out_dir / "units.jsonl"

    t0 = time.time()
    units: list = []
    with pdfplumber.open(pdf_path) as pdf:
        if pages_arg.lower() == "all":
            pages = list(range(len(pdf.pages)))
        else:
            pages = sorted({int(x) - 1 for x in pages_arg.split(",") if x.strip()})
        for pi in pages:
            n = process_page(pdf, pi, units)
            print(f"  p{pi+1}: +{n}", flush=True)
    with open(units_path, "a", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u.to_dict()) + "\n")
    print(f"DONE E/{project}: appended {len(units)} units in {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
