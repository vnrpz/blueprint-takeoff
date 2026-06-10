"""TZ R7 §1 — router must send each project to the expected branch.

PDFs live in Google Drive (data/raw is gitignored), so the routing DECISION
is tested here against each project's documented page signature. When the PDFs
are synced locally, test_router_on_pdfs (skipped otherwise) checks route_pdf
end-to-end.
"""
import os
import pytest
from src.router import classify, route_pdf, RouteSignals

# Documented per-project signatures (R6 findings + TZ R7 table):
#   4006 -> no schedule sheet, windows on elevations/plans  -> branch 3
#   745  -> schedule sheet on a RASTER page (sheet A1.0)     -> branch 2
#   OFR  -> schedule sheet with vector-extractable table     -> branch 1
#   1729 -> handwritten notes sheet                          -> branch 4
SIGNATURES = {
    "4006": RouteSignals(vector_page_frac=0.9, has_schedule_sheet=False,
                         schedule_is_vector=False, is_handwritten=False),
    "745":  RouteSignals(vector_page_frac=0.8, has_schedule_sheet=True,
                         schedule_is_vector=False, is_handwritten=False,
                         notation_profile="weather_shield", schedule_page_index=0),
    "OFR":  RouteSignals(vector_page_frac=0.95, has_schedule_sheet=True,
                         schedule_is_vector=True, is_handwritten=False),
    "1729": RouteSignals(vector_page_frac=0.05, has_schedule_sheet=False,
                         schedule_is_vector=False, is_handwritten=True),
}
EXPECTED = {"4006": 3, "745": 2, "OFR": 1, "1729": 4}


@pytest.mark.parametrize("proj", list(SIGNATURES))
def test_router_branch_selection(proj):
    r = classify(SIGNATURES[proj])
    assert r.branch == EXPECTED[proj], f"{proj}: got branch {r.branch} ({r.name}), want {EXPECTED[proj]}"


def test_branch_names():
    assert classify(SIGNATURES["745"]).name == "raster-table"
    assert classify(SIGNATURES["OFR"]).name == "vector-table"
    assert classify(SIGNATURES["4006"]).name == "elevations"
    assert classify(SIGNATURES["1729"]).name == "handwritten"


PROJECTS = {
    "4006": "data/raw/blueprint.pdf",
    "745":  "data/raw/745_Tamarack_Trail.pdf",
    "OFR":  "data/raw/4006_N_Sheridan-OFR-0573-2025-2.pdf",
    "1729": "data/raw/1729_Longvalley.pdf",
}


@pytest.mark.parametrize("proj,pdf", list(PROJECTS.items()))
def test_router_on_pdfs(proj, pdf):
    if not os.path.exists(pdf):
        pytest.skip(f"{pdf} not synced (Drive)")
    assert route_pdf(pdf).branch == EXPECTED[proj]
