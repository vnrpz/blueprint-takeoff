"""Pipeline interface — every variant implements run(pdf_path) -> list[Unit].
Each pipeline logs its intermediate artifacts to runs/<variant>/<project>/.
"""
from __future__ import annotations

import abc
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Iterable, Dict, Any

from src.schema import Unit
from src.vlm.base import VLMProvider


@dataclass
class PipelineRun:
    variant: str
    project: str
    pdf_path: Path
    units: List[Unit]
    elapsed_sec: float
    cost_usd: float = 0.0
    artifacts_dir: Optional[Path] = None
    notes: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class Pipeline(abc.ABC):
    name: str = "base"

    def __init__(self, vlm: VLMProvider, *, runs_root: str | Path = "runs"):
        self.vlm = vlm
        self.runs_root = Path(runs_root)

    def artifacts_dir(self, project: str) -> Path:
        d = self.runs_root / self.name / project
        d.mkdir(parents=True, exist_ok=True)
        return d

    @abc.abstractmethod
    def run(self, pdf_path: str | Path, *, project: Optional[str] = None) -> PipelineRun:
        ...

    @staticmethod
    def units_to_jsonl(units: Iterable[Unit], path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for u in units:
                f.write(json.dumps(u.to_dict()) + "\n")


EXTRACTION_PROMPT = """You are an expert window & door takeoff specialist.
Examine the image (a page from a construction PDF blueprint) and extract EVERY
window and door visible. Use the actual marks visible on the drawing (W1, W2,
D1, U1 etc.); fall back to G1, G2 only if no mark is visible. Return [] only
if there is truly no window or door content on this page.

Return ONLY a JSON array. Each element matches:
{
  "unit_id": "string (use mark from drawing if present, else G{n})",
  "kind": "window" | "door" | "composite",
  "panels": [{
    "role": "window" | "door",
    "width_in": <decimal inches; convert fractions like '36 3/16' to 36.1875>,
    "height_in": <decimal inches>,
    "glass": "tempered" | "annealed" | "mixed" | null,
    "u_factor": <number> | null,
    "egress": true | false | null,
    "clear_opening_sqft": <number> | null
  }],
  "qty": <integer>,
  "source_marks": ["string"],
  "color_interior": "string" | null,
  "color_exterior": "string" | null,
  "rough_opening": {"w_in": <number>, "h_in": <number>} | null,
  "evidence": [{"page": <int>, "region": "schedule"|"elevation"|"plan"|"notes"|"section", "bbox": [x,y,w,h]}],
  "confidence": <0..1>,
  "flags": [],
  "discovery_gaps": []
}

Rules:
- All measurements in decimal inches. Parse fractions.
- For composite units (window+door coupled, corner90 etc.), set kind="composite" and list every panel.
- If a value is not derivable from THIS page, return null and add to discovery_gaps.
- Output the JSON array only — no prose.
"""
