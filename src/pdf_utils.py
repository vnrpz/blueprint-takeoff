"""PDF utilities — rasterize, vector detect, page geometry.

Heavy work (300 DPI rasterization, OpenCV preprocess) lives here. Pipelines
import this module to avoid duplicating PDF plumbing.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# Lazy imports inside functions so unit tests on schema/normalize/matching
# can run without PyMuPDF / OpenCV installed.

@dataclass
class PageImage:
    page_index: int
    width_px: int
    height_px: int
    dpi: int
    image_path: Path
    is_vector: bool


def open_pdf(path: str | os.PathLike) -> "object":
    import fitz  # PyMuPDF
    return fitz.open(str(path))


def page_is_vector(page) -> bool:
    """Heuristic: a page is 'vector' if it has extractable text AND vector paths.

    Pure raster scans return 'is_vector=False' triggering Variant E fallback.
    """
    text = (page.get_text("text") or "").strip()
    has_text = len(text) > 50
    try:
        drawings = page.get_drawings()
        has_vectors = len(drawings) > 5
    except Exception:
        has_vectors = False
    return has_text and has_vectors


def rasterize(
    pdf_path: str | os.PathLike,
    out_dir: str | os.PathLike,
    dpi: int = 300,
    pages: Optional[List[int]] = None,
) -> List[PageImage]:
    """Rasterize all (or selected) pages to PNG at the given DPI."""
    import fitz
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    targets = pages if pages is not None else list(range(len(doc)))
    results: List[PageImage] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i in targets:
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = out / f"page_{i+1:03d}.png"
        pix.save(str(img_path))
        results.append(PageImage(
            page_index=i,
            width_px=pix.width,
            height_px=pix.height,
            dpi=dpi,
            image_path=img_path,
            is_vector=page_is_vector(page),
        ))
    doc.close()
    return results


def detect_regions(image_path: str | os.PathLike) -> List[Tuple[int, int, int, int]]:
    """OpenCV: detect rectangular regions on a sheet (Variant B).

    Returns bboxes in (x, y, w, h) pixels. Uses adaptive threshold + morphology
    to find frame borders. Filters by area to drop tiny noise.
    """
    import cv2
    import numpy as np
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    blurred = cv2.GaussianBlur(img, (5, 5), 0)
    thr = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 10
    )
    # Close gaps in border lines, then find external contours.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = img.shape
    min_area = (w * h) * 0.005  # 0.5% of the page
    boxes: List[Tuple[int, int, int, int]] = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw * ch < min_area:
            continue
        if cw < 80 or ch < 80:
            continue
        boxes.append((int(x), int(y), int(cw), int(ch)))
    # Sort top-to-bottom, left-to-right.
    boxes.sort(key=lambda b: (b[1] // 50, b[0]))
    return boxes


def grid_tiles(
    width: int, height: int, tile: int = 1024, overlap: float = 0.18
) -> Iterator[Tuple[int, int, int, int]]:
    """SAHI-style grid tiling (Variant C). Yields (x, y, w, h) in pixels."""
    step = int(tile * (1 - overlap))
    for y in range(0, max(1, height - tile + 1), step):
        for x in range(0, max(1, width - tile + 1), step):
            yield (x, y, tile, tile)
        # right-edge column
        yield (max(0, width - tile), y, tile, tile)
    # bottom row
    for x in range(0, max(1, width - tile + 1), step):
        yield (x, max(0, height - tile), tile, tile)
    yield (max(0, width - tile), max(0, height - tile), tile, tile)


def iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    """Intersection-over-Union for two (x, y, w, h) bboxes."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0
