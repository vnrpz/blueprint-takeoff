"""Variant D — coarse-to-fine pyramid (TZ §6.4)."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, List

from src.pdf_utils import rasterize
from src.pipelines.base import Pipeline, PipelineRun, EXTRACTION_PROMPT
from src.pipelines.parsing import parse_units
from src.schema import Unit


COARSE_PROMPT = """\nGive me ONLY a JSON list of rectangular regions of interest (windows/doors/schedules).
[{"region": "schedule|elevation|plan|notes", "bbox_pct": [x_pct, y_pct, w_pct, h_pct]}]
Coordinates are percentages 0..1 relative to the image."""


class VariantD(Pipeline):
    name = "variant_d"

    def run(self, pdf_path, *, project: Optional[str] = None) -> PipelineRun:
        from PIL import Image
        pdf_path = Path(pdf_path)
        project = project or pdf_path.stem
        out_dir = self.artifacts_dir(project)
        # Coarse pass at low DPI
        coarse_pages = rasterize(pdf_path, out_dir / "coarse", dpi=96)
        fine_pages = rasterize(pdf_path, out_dir / "fine", dpi=300)
        all_units: List[Unit] = []
        cost = 0.0
        errs: list[str] = []
        t0 = time.time()
        for c, f in zip(coarse_pages, fine_pages):
            r = self.vlm.extract(c.image_path, COARSE_PROMPT)
            cost += r.cost_usd
            regions = r.parsed_json or []
            if not isinstance(regions, list):
                regions = []
            full = Image.open(f.image_path)
            W, H = full.size
            for k, reg in enumerate(regions):
                bb = reg.get("bbox_pct") or [0, 0, 1, 1]
                try:
                    x = int(bb[0] * W); y = int(bb[1] * H)
                    w = int(bb[2] * W); h = int(bb[3] * H)
                except Exception:
                    continue
                if w < 50 or h < 50:
                    continue
                crop = out_dir / f"page_{f.page_index+1:03d}_r{k:03d}.png"
                full.crop((x, y, x + w, y + h)).save(crop)
                rr = self.vlm.extract(crop, EXTRACTION_PROMPT)
                cost += rr.cost_usd
                if rr.error:
                    errs.append(f"p{f.page_index+1} r{k}: {rr.error}")
                    continue
                page_units = parse_units(rr.parsed_json)
                for u in page_units:
                    for ev in u.evidence:
                        if ev.page == 0:
                            ev.page = f.page_index + 1
                        if ev.bbox and len(ev.bbox) == 4:
                            bx, by, bw, bh = ev.bbox
                            ev.bbox = (x + bx, y + by, bw, bh)
                all_units.extend(page_units)
        Pipeline.units_to_jsonl(all_units, out_dir / "units.jsonl")
        return PipelineRun(variant=self.name, project=project, pdf_path=pdf_path,
                           units=all_units, elapsed_sec=time.time() - t0, cost_usd=cost,
                           artifacts_dir=out_dir, errors=errs)
