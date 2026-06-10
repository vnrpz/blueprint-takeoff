
"""Branch 1 — vector-table extraction for printed offer/order forms (OFR).

Parses a per-unit offer PDF (Frame size / Rough opening / qty / glass /
egress per offer line) into the common eval schema, and reconciles the
line economics (unit_price x qty == line total) as an honesty check.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF

_FRAME_RX = re.compile(r"Frame size:\s*([0-9].*?)\s*$", re.M)
_RO_RX = re.compile(r"Rough opening:\s*([0-9].*?)\s*$", re.M)
_DIM_RX = re.compile(r"([0-9]+(?:\s+\d+/\d+)?)\s*\"?\s*[xX]\s*([0-9]+(?:\s+\d+/\d+)?)")
_MONEY_RX = re.compile(r"-?\d{1,3}(?:,\d{3})*(?:\.\d{2})")
_GLASS_TEMP = re.compile(r"\bTEMP\b")
_GLASS_ANN = re.compile(r"\bANN\b")


def _frac_to_float(s: str) -> float:
    s = s.strip().replace('"', "")
    parts = s.split()
    total = 0.0
    for p in parts:
        if "/" in p:
            a, b = p.split("/")
            total += float(a) / float(b)
        else:
            total += float(p)
    return total


@dataclass
class OfrUnit:
    item: str
    frame_w: Optional[float]
    frame_h: Optional[float]
    ro_w: Optional[float]
    ro_h: Optional[float]
    qty: int
    glass: str          # "tempered" | "annealed" | "mixed" | "unknown"
    egress: bool
    unit_price: Optional[float] = None
    line_total: Optional[float] = None


@dataclass
class OfrExtract:
    units: list = field(default_factory=list)
    total_qty: int = 0
    reconciled: bool = False
    recon_detail: list = field(default_factory=list)


_PRICEBLOCK_RX = re.compile(
    r"(\d+)\n([\d,]+\.\d{2})\n-\n([\d,]+\.\d{2})\n-\n(\d+)\n([\d,]+\.\d{2})\n([\d,]+\.\d{2})\nAccessories")


def _parse_qty_price(page_text: str):
    """Return (item_no, unit_price, line_total, qty) from the offer price block."""
    m = _PRICEBLOCK_RX.search(page_text)
    if not m:
        return None, None, None, None
    item_no = m.group(1)
    unit_price = float(m.group(3).replace(",", ""))
    qty = int(m.group(4))
    line_total = float(m.group(5).replace(",", ""))
    return item_no, unit_price, line_total, qty


def _glass_kind(block: str) -> str:
    has_t = bool(_GLASS_TEMP.search(block))
    has_a = bool(_GLASS_ANN.search(block))
    if has_t and has_a:
        return "mixed"
    if has_t:
        return "tempered"
    if has_a:
        return "annealed"
    return "unknown"


def extract_ofr(path: str) -> OfrExtract:
    doc = fitz.open(path)
    out = OfrExtract()
    line_qtys = []
    for i, page in enumerate(doc):
        t = page.get_text("text") or ""
        if "Frame size:" not in t:
            continue
        ro = _RO_RX.search(t)
        ro_w = ro_h = None
        if ro:
            dm = _DIM_RX.search(ro.group(1))
            if dm:
                ro_w, ro_h = _frac_to_float(dm.group(1)), _frac_to_float(dm.group(2))
        item_no, unit_price, line_total, qty = _parse_qty_price(t)
        # split into per-unit sub-blocks (each starts at "Profile:")
        idxs = [m.start() for m in re.finditer(r"Profile:", t)]
        blocks = []
        for k, s in enumerate(idxs):
            e = idxs[k + 1] if k + 1 < len(idxs) else len(t)
            blocks.append(t[s:e])
        if not blocks:
            blocks = [t]
        n_sub = len(blocks)
        for j, blk in enumerate(blocks):
            fm = _FRAME_RX.search(blk)
            fw = fh = None
            if fm:
                dm = _DIM_RX.search(fm.group(1))
                if dm:
                    fw, fh = _frac_to_float(dm.group(1)), _frac_to_float(dm.group(2))
            egress = bool(re.search(r"Egress:\s*YES", blk))
            out.units.append(OfrUnit(
                item=f"{item_no or i + 1}.{j + 1}" if n_sub > 1 else f"{item_no or i + 1}",
                frame_w=fw, frame_h=fh, ro_w=ro_w, ro_h=ro_h,
                qty=qty or 0, glass=_glass_kind(blk), egress=egress,
                unit_price=unit_price, line_total=line_total,
            ))
        if unit_price and line_total and qty:
            ok = abs(unit_price * qty - line_total) < 0.5
            out.recon_detail.append({"page": i + 1, "item": item_no, "unit_price": unit_price,
                                     "qty": qty, "line_total": line_total, "ok": ok})
            line_qtys.append(qty)
    out.total_qty = sum(line_qtys)
    out.reconciled = bool(out.recon_detail) and all(d["ok"] for d in out.recon_detail)
    return out


def to_schema(ex: OfrExtract) -> dict:
    """Map to the common eval schema (groups -> units)."""
    units = []
    for u in ex.units:
        units.append({
            "mark": u.item,
            "width": u.frame_w, "height": u.frame_h,
            "rough_opening_width": u.ro_w, "rough_opening_height": u.ro_h,
            "qty": u.qty,
            "glass": u.glass,
            "egress": bool(u.egress),
        })
    return {"groups": [{"mark": "OFR", "units": units}],
            "total_qty": ex.total_qty,
            "reconciled": ex.reconciled}
