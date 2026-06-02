"""Variant C — overlap grid tiling + IoU dedup (SAHI-style, TZ §6.3)."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, List

from src.pdf_utils import rasterize, grid_tiles, iou
from src.pipelines.base import Pipeline, PipelineRun, EXTRACTION_PROMPT
from src.pipelines.parsing import parse_units
from src.schema import Unit
from src.normalize import spec_group_key


class VariantC(Pipeline):
    name = "variant_c"

    def run(self, pdf_path, *, project: Optional[str] = None) -> PipelineRun:
        from PIL import Image
        pdf_path = Path(pdf_path)
        project = project or pdf_path.stem
        out_dir = self.artifacts_dir(project)
        pages = rasterize(pdf_path, out_dir / "pages", dpi=300)
        accum: List[Unit] = []
        cost = 0.0
        errs: list[str] = []
        t0 = time.time()
        for p in pages:
            img = Image.open(p.image_path)
            tiles = list(grid_tiles(p.width_px, p.height_px, tile=1024, overlap=0.18))
            for k, (x, y, w, h) in enumerate(tiles):
                tile = out_dir / f"page_{p.page_index+1:03d}_tile_{k:03d}.png"
                img.crop((x, y, x + w, y + h)).save(tile)
                r = self.vlm.extract(tile, EXTRACTION_PROMPT)
                cost += r.cost_usd
                if r.error:
                    errs.append(f"p{p.page_index+1} t{k}: {r.error}")
                    continue
                tile_units = parse_units(r.parsed_json)
                for u in tile_units:
                    for ev in u.evidence:
                        if ev.page == 0:
                            ev.page = p.page_index + 1
                        if ev.bbox and len(ev.bbox) == 4:
                            bx, by, bw, bh = ev.bbox
                            ev.bbox = (x + bx, y + by, bw, bh)
                accum.extend(tile_units)
        # Dedup: same spec-group key AND IoU(bbox) > 0.4 -> keep highest confidence
        deduped: List[Unit] = []
        for u in accum:
            keep = True
            k_u = spec_group_key(u)
            for d in deduped:
                if spec_group_key(d) != k_u:
                    continue
                bbs_u = [tuple(e.bbox) for e in u.evidence if e.bbox]
                bbs_d = [tuple(e.bbox) for e in d.evidence if e.bbox]
                if any(iou(a, b) > 0.4 for a in bbs_u for b in bbs_d):
                    keep = False
                    if u.confidence > d.confidence:
                        d.confidence = u.confidence
                        d.qty = max(d.qty, u.qty)
                    break
            if keep:
                deduped.append(u)
        Pipeline.units_to_jsonl(deduped, out_dir / "units.jsonl")
        return PipelineRun(variant=self.name, project=project, pdf_path=pdf_path,
                           units=deduped, elapsed_sec=time.time() - t0, cost_usd=cost,
                           artifacts_dir=out_dir, errors=errs)
