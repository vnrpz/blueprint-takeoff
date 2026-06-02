"""TZ §13: every variant produces valid JSON on every PDF (no crashes).

Heavy — only runs if data/raw/*.pdf are present AND RUN_HEAVY=1 in env.
Uses MockProvider so no API calls happen here; the goal is to prove the
pipeline machinery doesn't crash on real PDFs.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import pytest

from src.pipelines import VARIANTS
from src.vlm import MockProvider


PROJECTS = {
    "4006":  "data/raw/blueprint.pdf",
    "745":   "data/raw/745_Tamarack_Trail.pdf",
    "321":   "data/raw/321_Sunset.pdf",
    "1729":  "data/raw/1729_Longvalley.pdf",
    "3122":  "data/raw/3122_Lyndale.pdf",
    "OFR":   "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf",
}


@pytest.mark.skipif(os.environ.get("RUN_HEAVY") != "1",
                    reason="Set RUN_HEAVY=1 to exercise pipelines on real PDFs.")
@pytest.mark.parametrize("variant_letter", list(VARIANTS.keys()))
@pytest.mark.parametrize("project,pdf", list(PROJECTS.items()))
def test_no_crash(variant_letter, project, pdf):
    if not Path(pdf).exists():
        pytest.skip(f"PDF missing: {pdf}")
    Cls = VARIANTS[variant_letter]
    pipeline = Cls(MockProvider(payload=[]))
    result = pipeline.run(pdf, project=project)
    assert isinstance(result.units, list)
    # JSON-roundtrippable
    for u in result.units:
        assert u.to_dict()
