"""Variant B — semantic region tiling (TZ §6.2)."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional

from src.pdf_utils import rasterize, detect_regions
from src.pipelines.base import Pipeline, PipelineRun, EXTRACTION_PROMPT
from src.pipelines.parsing import parse_units
from src.schema import Unit


REGION_PROMPT_HINT = """\nFOCUS: this crop is a single drawing region. Classify it as schedule / elevation / plan / notes / section (state in evidence). Extract ONLY items visible in this region."""


class VariantB(Pipeline):
    name = "variant_b"

    def run(self, pdf_path, *, project: Optional[str] = None) -> PipelineRun:
        from PIL import Image  # lazy
        pdf_path = Path(pdf_path)
        project = project or pdf_path.stem
        out_dir = self.artifacts_dir(project)
        pages = rasterize(pdf_path, out_dir / "pages", dpi=300)
        all_units: list[Unit] = []
        cost = 0.0
        errs: list[str] = []
        t0 = time.time()
        for p in pages:
            boxes = detect_regions(p.image_path)
            img = Image.open(p.image_path)
            crops_dir = out_dir / f"page_{p.page_index+1:03d}_regions"
            crops_dir.mkdir(parents=True, exist_ok=True)
            for k, (x, y, w, h) in enumerate(boxes):
                crop_path = crops_dir / f"r{k:03d}.png"
                img.crop((x, y, x + w, y + h)).save(crop_path)
                result = self.vlm.extract(crop_path, EXTRACTION_PROMPT + REGION_PROMPT_HINT)
                cost += result.cost_usd
                if result.error:
                    errs.append(f"p{p.page_index+1} r{k}: {result.error}")
                    continue
                units = parse_units(result.parsed_json)
                for u in units:
                    for ev in u.evidence:
                        if ev.page == 0:
                            ev.page = p.page_index + 1
                        # Re-anchor bbox to page coords
                        if ev.bbox and len(ev.bbox) == 4:
                            bx, by, bw, bh = ev.bbox
                            ev.bbox = (x + bx, y + by, bw, bh)
                all_units.extend(units)
        Pipeline.units_to_jsonl(all_units, out_dir / "units.jsonl")
        return PipelineRun(variant=self.name, project=project, pdf_path=pdf_path,
                           units=all_units, elapsed_sec=time.time() - t0, cost_usd=cost,
                           artifacts_dir=out_dir, errors=errs)
