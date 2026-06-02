"""Variant A — whole-page VLM baseline (TZ §6.1)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from src.pdf_utils import rasterize
from src.pipelines.base import Pipeline, PipelineRun, EXTRACTION_PROMPT
from src.pipelines.parsing import parse_units
from src.schema import Unit


class VariantA(Pipeline):
    name = "variant_a"

    def run(self, pdf_path, *, project: Optional[str] = None) -> PipelineRun:
        pdf_path = Path(pdf_path)
        project = project or pdf_path.stem
        out_dir = self.artifacts_dir(project)
        pages = rasterize(pdf_path, out_dir / "pages", dpi=300)
        all_units: list[Unit] = []
        cost = 0.0
        errs: list[str] = []
        t0 = time.time()
        for p in pages:
            result = self.vlm.extract(p.image_path, EXTRACTION_PROMPT)
            cost += result.cost_usd
            if result.error:
                errs.append(f"page {p.page_index + 1}: {result.error}")
                continue
            page_units = parse_units(result.parsed_json)
            for u in page_units:
                for ev in u.evidence:
                    if ev.page == 0:
                        ev.page = p.page_index + 1
            all_units.extend(page_units)
            # Save artifact
            (out_dir / f"page_{p.page_index+1:03d}.json").write_text(result.raw_text)
        # Save final units
        Pipeline.units_to_jsonl(all_units, out_dir / "units.jsonl")
        return PipelineRun(
            variant=self.name, project=project, pdf_path=pdf_path,
            units=all_units, elapsed_sec=time.time() - t0, cost_usd=cost,
            artifacts_dir=out_dir, errors=errs,
        )
