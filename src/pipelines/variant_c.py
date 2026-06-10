"""Variant C - overlap grid tiling + IoU dedup (SAHI-style, TZ §6.3).

R6 cost gate (see docs/r6_variant_c_cost_gate.md):
  * Default tiling is now (tile=2048, overlap=0) - one bullet of the
    cost-gate options; the previous (1024, 0.18) blew up to 200-300 tiles
    per raster page on 745 and never finished within budget.
  * Raster pages are SKIPPED with a clear `skipped_reason`. Variant C is
    only appropriate for vector pages; on raster scans like 745 the entire
    tile pipeline degenerates into "many crops of the same blurry image".
  * If ALL pages in a project are raster the whole PipelineRun records
    skipped_reason="all_pages_raster" and zero cost / zero units, instead
    of silently producing an empty leaderboard cell.
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, List

from src.pdf_utils import rasterize, grid_tiles, iou
from src.pipelines.base import Pipeline, PipelineRun, EXTRACTION_PROMPT
from src.pipelines.parsing import parse_units
from src.schema import Unit
from src.normalize import spec_group_key


# R6 defaults - bigger tile, no overlap. Override per-call via env if needed.
DEFAULT_TILE_PX = 2048
DEFAULT_OVERLAP = 0.0


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
        skipped_pages: list[int] = []
        t0 = time.time()
        for p in pages:
            if not p.is_vector:
                # R6 cost gate: do not tile raster pages.
                skipped_pages.append(p.page_index + 1)
                continue
            img = Image.open(p.image_path)
            tiles = list(grid_tiles(p.width_px, p.height_px,
                                    tile=DEFAULT_TILE_PX, overlap=DEFAULT_OVERLAP))
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
        # R6 honest reporting: surface raster skips, do not produce a silent empty cell.
        if skipped_pages:
            errs.append(f"raster pages skipped (R6 cost gate): {len(skipped_pages)}/{len(pages)} pages [{','.join(str(s) for s in skipped_pages[:10])}{'...' if len(skipped_pages)>10 else ''}]")
        if len(skipped_pages) == len(pages):
            errs.append("all_pages_raster: Variant C not applicable; see docs/r6_variant_c_cost_gate.md")
        return PipelineRun(variant=self.name, project=project, pdf_path=pdf_path,
                           units=deduped, elapsed_sec=time.time() - t0, cost_usd=cost,
                           artifacts_dir=out_dir, errors=errs)
