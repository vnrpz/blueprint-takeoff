"""Shared test fixtures / helpers.

Centralizes two things every test file previously open-coded:

1. Putting the repo root on ``sys.path`` so ``import src.*`` / ``import eval.*``
   works when pytest is invoked from any directory.
2. A uniform "skip if the gitignored input PDF is absent" gate, so a clean
   checkout (no ``data/raw/*.pdf``) runs green instead of hard-failing — the
   same contract ``tests/test_no_crash_all_projects.py`` already follows.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def require_pdf(rel_path: str) -> str:
    """Return an absolute path to a data PDF, or skip the test if it's absent.

    Real blueprints live in ``data/raw/`` which is gitignored, so they are not
    present on CI or a fresh clone. Tests that genuinely need a real PDF should
    funnel through here so they skip cleanly instead of erroring.
    """
    p = REPO_ROOT / rel_path
    if not p.exists():
        pytest.skip(f"input PDF absent (gitignored): {rel_path}")
    return str(p)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
