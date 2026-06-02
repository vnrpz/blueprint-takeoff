"""Variant E — vector-first hybrid (TZ §6.5)."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, List

from src.pdf_utils import rasterize, page_is_vector
from src.pipelines.base import Pipeline, PipelineRun
from src.pipelines.parsing import parse_units
from src.pipelines.variant_b import VariantB
from src.schema import Unit, Panel
from src.normalize import parse_inches


SCHEDULE_HEADERS = {"mark", "size", "width", "height", "type", "glass", "u-factor", "u factor", "egress"}


class VariantE(Pipeline):
    name = "variant_e"

    def run(self, pdf_path, *, project: Optional[str] = None) -> PipelineRun:
        import fitz
        import pdfplumber
        pdf_path = Path(pdf_path)
        project = project or pdf_path.stem
        out_dir = self.artifacts_dir(project)
        t0 = time.time()
        doc = fitz.open(str(pdf_path))
        is_vector_any = any(page_is_vector(p) for p in doc)
        doc.close()
        units: List[Unit] = []
        errs: list[str] = []
        cost = 0.0
        if is_vector_any:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for pi, page in enumerate(pdf.pages):
                    for tbl in (page.extract_tables() or []):
                        if not tbl or not tbl[0]:
                            continue
                        header = [str(c or "").strip().lower() for c in tbl[0]]
                        if not any(h in SCHEDULE_HEADERS for h in header):
                            continue
                        cols = {h: idx for idx, h in enumerate(header)}
                        for row in tbl[1:]:
                            try:
                                row = [str(c or "").strip() for c in row]
                                mark = row[cols.get("mark", 0)] if "mark" in cols else f"R{pi}-{len(units)}"
                                size_col = cols.get("size") or cols.get("size (w x h)")
                                width = height = None
                                if size_col is not None and "x" in row[size_col].lower():
                                    w_s, _, h_s = row[size_col].lower().partition("x")
                                    width = parse_inches(w_s.strip())
                                    height = parse_inches(h_s.strip())
                                if width is None and "width" in cols:
                                    width = parse_inches(row[cols["width"]])
                                if height is None and "height" in cols:
                                    height = parse_inches(row[cols["height"]])
                                if width is None or height is None:
                                    continue
                                glass = row[cols["glass"]].lower() if "glass" in cols and row[cols["glass"]] else None
                                if glass and "temp" in glass: glass = "tempered"
                                elif glass and ("ann" in glass): glass = "annealed"
                                elif glass and "mix" in glass: glass = "mixed"
                                else: glass = None
                                u_factor = None
                                for h in ("u-factor", "u factor"):
                                    if h in cols and row[cols[h]]:
                                        try: u_factor = float(row[cols[h]].split()[0]); break
                                        except Exception: pass
                                egress = None
                                if "egress" in cols:
                                    s = row[cols["egress"]].lower()
                                    if s in ("y", "yes", "true"): egress = True
                                    elif s in ("n", "no", "false"): egress = False
                                qty_col = cols.get("qty") or cols.get("quantity") or cols.get("count")
                                qty = 1
                                if qty_col is not None:
                                    try: qty = int(row[qty_col])
                                    except Exception: qty = 1
                                units.append(Unit(
                                    unit_id=mark,
                                    kind="door" if mark.upper().startswith("D") else "window",
                                    panels=[Panel(role="door" if mark.upper().startswith("D") else "window",
                                                  width_in=width, height_in=height,
                                                  glass=glass, u_factor=u_factor, egress=egress)],
                                    qty=qty,
                                    source_marks=[mark],
                                    confidence=0.95,
                                ))
                            except Exception:
                                continue
        if not units:  # fallback to Variant B for raster pages
            b = VariantB(self.vlm, runs_root=self.runs_root)
            r = b.run(pdf_path, project=project + "_E_fallback_B")
            return PipelineRun(variant=self.name, project=project, pdf_path=pdf_path,
                               units=r.units, elapsed_sec=time.time() - t0, cost_usd=r.cost_usd,
                               artifacts_dir=out_dir, errors=r.errors,
                               notes={"fallback": "B"})
        Pipeline.units_to_jsonl(units, out_dir / "units.jsonl")
        return PipelineRun(variant=self.name, project=project, pdf_path=pdf_path,
                           units=units, elapsed_sec=time.time() - t0, cost_usd=cost,
                           artifacts_dir=out_dir, errors=errs,
                           notes={"mode": "vector"})
