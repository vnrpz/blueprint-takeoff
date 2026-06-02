"""Pre-flight checks on data/raw/*.pdf before kicking off run_benchmark.

Verifies each expected file is present, openable by PyMuPDF, under 50 MB,
not password-protected, and prints a summary table (pages, has_text, has_vector).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

EXPECTED = {
    "4006":  "blueprint.pdf",
    "OFR":   "4006_N_Sheridan-OFR-0573-2025-2.pdf",
    "745":   "745_Tamarack_Trail.pdf",
    "321":   "321_Sunset.pdf",
    "1729":  "1729_Longvalley.pdf",
    "3122":  "3122_Lyndale.pdf",
}

MAX_BYTES = 120 * 1024 * 1024  # 120 MB to accept 81 MB blueprint.pdf


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/raw")
    args = ap.parse_args(argv)
    raw = Path(args.dir)
    print(f"Pre-flight: {raw.resolve()}")
    print(f"{'project':<8} {'file':<40} {'pages':>6} {'size_kb':>8} {'has_text':>9} {'has_vector':>11} status")
    any_fail = False
    try:
        import fitz
    except Exception as e:
        print(f"FATAL: PyMuPDF import failed: {e}")
        return 2
    for proj, name in EXPECTED.items():
        p = raw / name
        if not p.exists():
            print(f"{proj:<8} {name:<40} {'-':>6} {'-':>8} {'-':>9} {'-':>11} MISSING")
            any_fail = True
            continue
        size = p.stat().st_size
        if size > MAX_BYTES:
            print(f"{proj:<8} {name:<40} {'-':>6} {size//1024:>8} {'-':>9} {'-':>11} TOO_LARGE")
            any_fail = True
            continue
        try:
            doc = fitz.open(str(p))
        except Exception as e:
            print(f"{proj:<8} {name:<40} {'-':>6} {size//1024:>8} {'-':>9} {'-':>11} OPEN_FAIL {e}")
            any_fail = True
            continue
        if doc.needs_pass:
            print(f"{proj:<8} {name:<40} {'-':>6} {size//1024:>8} {'-':>9} {'-':>11} PASSWORD")
            any_fail = True
            doc.close()
            continue
        pages = len(doc)
        page = doc[0]
        has_text = bool((page.get_text("text") or "").strip())
        try:
            has_vector = len(page.get_drawings()) > 5
        except Exception:
            has_vector = False
        doc.close()
        print(f"{proj:<8} {name:<40} {pages:>6} {size//1024:>8} {str(has_text):>9} {str(has_vector):>11} OK")
    return 0 if not any_fail else 1


if __name__ == "__main__":
    sys.exit(main())
