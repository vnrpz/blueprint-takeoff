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


EXTRACTION_PROMPT = """You are looking at one page from a construction PDF blueprint. Extract every window and door visible. Return ONLY a JSON array (or [] if nothing visible).

Each element:
{"unit_id": "W1 etc. from the drawing or G1 fallback", "kind": "window|door|composite", "panels": [{"role": "window|door", "width_in": <decimal inches; convert fractions like '36 3/16' to 36.1875>, "height_in": <decimal>, "glass": "tempered|annealed|mixed" or null, "u_factor": <number> or null, "egress": true|false|null, "clear_opening_sqft": <number> or null}], "qty": <integer>, "source_marks": ["W1"], "evidence": [{"page": 1, "region": "schedule|elevation|plan|notes|section", "bbox": [x,y,w,h]}], "confidence": <0-1>, "flags": [], "discovery_gaps": []}

Be specific. If you see a window/door, output it. Use the actual marks (W1, W2, D1, U1) visible on the drawing. For composites (window+door coupled, corner90 etc.) set kind="composite" and list every panel. Output the JSON array only — no prose, no fences.
"""
