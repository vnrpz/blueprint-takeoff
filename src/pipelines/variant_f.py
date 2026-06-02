"""Variant F — multi-agent reconciliation + neuro-symbolic IRC checks (TZ §6.6, §11)."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, List, Dict

from src.pdf_utils import rasterize, detect_regions
from src.pipelines.base import Pipeline, PipelineRun, EXTRACTION_PROMPT
from src.pipelines.parsing import parse_units
from src.schema import Unit
from src.normalize import spec_group_key


AGENT_PROMPTS = {
    "schedule": EXTRACTION_PROMPT + "\nFOCUS: Window/Door Schedule table only. Each row = one mark; the schedule states qty.",
    "elevation": EXTRACTION_PROMPT + "\nFOCUS: Elevation views. Count windows/doors visible; cross-check against schedule.",
    "plan": EXTRACTION_PROMPT + "\nFOCUS: Floor-plan view. Annotate where each marked opening lives, room labels if visible.",
    "notes": EXTRACTION_PROMPT + "\nFOCUS: General notes / energy table / IRC references. Report U-factor limits, tempered zones, egress callouts."
}


# --- Neuro-symbolic helpers (TZ §11)
def _clear_opening_sqft(p_w_in: float, p_h_in: float) -> float:
    return (p_w_in * p_h_in) / 144.0


def _apply_neuro_symbolic(units: List[Unit]) -> None:
    """In-place flag attachment based on geometry (no VLM)."""
    for u in units:
        for p in u.panels:
            # R310 (egress): clear opening >= 5.7 sqft
            if p.egress and p.clear_opening_sqft is not None and p.clear_opening_sqft < 5.7:
                u.flags.append("irc_r310_egress_undersize")
            # R308.4: tempered required if w*h > 9 sqft AND near floor (we don't have sill)
            if p.glass == "annealed" and (p.width_in * p.height_in / 144.0) > 9.0:
                u.flags.append("irc_r308_4_likely_tempered_required")
        # composite sanity
        if u.kind == "composite" and len(u.panels) < 2:
            u.flags.append("composite_panel_count_mismatch")


class VariantF(Pipeline):
    name = "variant_f"

    def run(self, pdf_path, *, project: Optional[str] = None) -> PipelineRun:
        from PIL import Image
        pdf_path = Path(pdf_path)
        project = project or pdf_path.stem
        out_dir = self.artifacts_dir(project)
        pages = rasterize(pdf_path, out_dir / "pages", dpi=300)
        agent_outputs: Dict[str, List[Unit]] = {k: [] for k in AGENT_PROMPTS}
        cost = 0.0
        errs: list[str] = []
        t0 = time.time()
        for p in pages:
            img = Image.open(p.image_path)
            for k, (x, y, w, h) in enumerate(detect_regions(p.image_path)):
                crop = out_dir / f"page_{p.page_index+1:03d}_r{k:03d}.png"
                img.crop((x, y, x + w, y + h)).save(crop)
                # Each agent reads every region; agent's prompt biases what it returns.
                for agent_name, prompt in AGENT_PROMPTS.items():
                    r = self.vlm.extract(crop, prompt)
                    cost += r.cost_usd
                    if r.error:
                        errs.append(f"{agent_name} p{p.page_index+1} r{k}: {r.error}")
                        continue
                    for u in parse_units(r.parsed_json):
                        for ev in u.evidence:
                            if ev.page == 0: ev.page = p.page_index + 1
                            if ev.bbox and len(ev.bbox) == 4:
                                bx, by, bw, bh = ev.bbox
                                ev.bbox = (x + bx, y + by, bw, bh)
                        agent_outputs[agent_name].append(u)
        # Reconciliation: group by spec key, take consensus qty from {schedule, elevation, plan}
        consensus: Dict = {}
        for agent_name, units in agent_outputs.items():
            for u in units:
                key = spec_group_key(u)
                bucket = consensus.setdefault(key, {
                    "agents": {}, "evidence": [], "marks": set(),
                    "panels": u.panels, "kind": u.kind,
                })
                bucket["agents"].setdefault(agent_name, []).append(u.qty)
                bucket["evidence"].extend(u.evidence)
                bucket["marks"].update(u.source_marks)
        final: List[Unit] = []
        for i, (k, b) in enumerate(consensus.items()):
            qtys = b["agents"]
            consensus_sources = []
            for src in ("schedule", "elevation", "plan"):
                if qtys.get(src):
                    consensus_sources.append(max(qtys[src]))
            qty = max(consensus_sources) if consensus_sources else max(max(v) for v in qtys.values())
            flags: list[str] = []
            # Disagreement flag if sources differ by >1
            if len(consensus_sources) >= 2 and (max(consensus_sources) - min(consensus_sources)) > 1:
                flags.append("qty_mismatch_facade_schedule")
            # Mark missing from schedule?
            if "schedule" not in qtys and ("plan" in qtys or "elevation" in qtys):
                flags.append("mark_missing_from_schedule")
            final.append(Unit(
                unit_id=("|".join(sorted(b["marks"])) or f"F{i+1}"),
                kind=b["kind"],
                panels=b["panels"],
                qty=qty,
                source_marks=sorted(b["marks"]),
                evidence=b["evidence"],
                confidence=min(1.0, 0.5 + 0.15 * len(qtys)),  # more agents agree → higher conf
                flags=flags,
                discovery_gaps=[],
            ))
        _apply_neuro_symbolic(final)
        Pipeline.units_to_jsonl(final, out_dir / "units.jsonl")
        return PipelineRun(variant=self.name, project=project, pdf_path=pdf_path,
                           units=final, elapsed_sec=time.time() - t0, cost_usd=cost,
                           artifacts_dir=out_dir, errors=errs)
