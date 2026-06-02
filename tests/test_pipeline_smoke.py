"""Smoke tests for the pipeline machinery.

Builds a tiny synthetic PDF in-process, runs each variant with a MockProvider
returning a canned unit, and asserts no crashes + valid output shape.

This is the regression backstop that fired before real PDFs arrived.
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from src.pipelines import VARIANTS
from src.vlm import MockProvider
from src.schema import Unit


CANNED = [{
    "unit_id": "W1",
    "kind": "window",
    "panels": [{"role": "window", "width_in": 72.5, "height_in": 88.5,
                "glass": "mixed", "u_factor": 0.24, "egress": True}],
    "qty": 63,
    "source_marks": ["W1"],
    "evidence": [{"page": 1, "region": "schedule", "bbox": [40, 40, 460, 100]}],
    "confidence": 0.9,
}]


@pytest.fixture(scope="module")
def smoke_pdf(tmp_path_factory):
    fitz = pytest.importorskip("fitz")
    d = tmp_path_factory.mktemp("smoke")
    pdf = d / "smoke.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 50), "WINDOW SCHEDULE", fontsize=14)
    page.insert_text((50, 80), "Mark  Size       Glass   U      Egress  Qty", fontsize=10)
    page.insert_text((50, 100), "W1    72.5x88.5  mixed   0.24   Y       63", fontsize=10)
    page.draw_rect(fitz.Rect(40, 40, 500, 140), width=1)
    page.draw_rect(fitz.Rect(50, 200, 200, 350), width=1)
    doc.save(str(pdf))
    doc.close()
    return pdf


@pytest.mark.parametrize("letter", list(VARIANTS.keys()))
def test_variant_no_crash(letter, smoke_pdf, tmp_path):
    Cls = VARIANTS[letter]
    pipeline = Cls(MockProvider(payload=CANNED), runs_root=tmp_path)
    result = pipeline.run(smoke_pdf, project=f"smoke_{letter}")
    assert isinstance(result.units, list)
    assert result.elapsed_sec >= 0
    # Each output unit must serialise to dict and back without losing shape.
    for u in result.units:
        d = u.to_dict()
        u2 = Unit.from_dict(d)
        assert u2.kind == u.kind
        assert u2.qty == u.qty
