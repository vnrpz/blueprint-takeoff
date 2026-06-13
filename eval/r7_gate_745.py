import os, sys, json
from pathlib import Path

# Resolve repo root relative to this file (no machine-specific absolute paths).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
os.chdir(_REPO_ROOT)

from src.pdf_utils import rasterize
from src.notation import decode, NotationError
from src.schema import Unit, Panel
from src.normalize import group_units
from eval.metrics import evaluate
from src import vlm

PROMPT = (
 "You are reading sheet A1.0 of a residential construction blueprint (Weather Shield windows). "
 "Find the WINDOW/DOOR SCHEDULE table. Transcribe EVERY row of THAT TABLE ONLY. "
 "Ignore floor plans, elevations and any windows drawn on them — only the schedule table rows. "
 "For each row return an object: "
 '{"mark":"<mark e.g. A>","size_code":"<raw code exactly as printed e.g. 2870 or 2-2870 or 3180>",'
 '"qty":<integer from the QTY column>,"type":"window" or "door","remarks":"<remarks or empty>"}. '
 "Return ONLY a JSON array. Do NOT convert the size code — return it raw."
)

def render():
    pages = rasterize("data/raw/745_Tamarack_Trail.pdf", "/tmp/r7_render", dpi=300, pages=[0])
    return str(pages[0].image_path)

def rows_to_units(rows):
    units=[]
    for r in rows or []:
        code=str(r.get("size_code","")).strip()
        try: qty=int(r.get("qty") or 0)
        except: qty=0
        typ=str(r.get("type","")).lower()
        kind="door" if typ.startswith("d") else "window"
        try:
            d=decode(code,"weather_shield")
        except NotationError:
            continue
        role="door" if kind=="door" else "window"
        units.append(Unit(unit_id=str(r.get("mark","?")), kind=kind, qty=qty,
            panels=[Panel(role=role, width_in=float(d.width_in), height_in=float(d.height_in))],
            source_marks=[str(r.get("mark","")), code]))
    return units

def run_model(spec, img):
    try:
        p=vlm.get_provider(spec)
        res=p.extract(img, PROMPT)
        if res.error:
            return None, f"ERR {res.error}", res.cost_usd
        data=res.parsed_json
        if data is None:
            # try parse raw
            import re
            m=re.search(r"\[.*\]", res.raw_text, re.S)
            data=json.loads(m.group(0)) if m else None
        return data, None, res.cost_usd
    except Exception as e:
        return None, f"EXC {type(e).__name__}: {e}", 0.0

def main():
    img=render()
    print("rendered:", img)
    gt=[Unit.from_dict(u) for u in json.load(open("tests/ground_truth/745_extract.json"))["units"]]
    gt_total=sum(u.qty for u in gt)
    print("GT units:", len(gt), "GT total qty:", gt_total)
    results={}
    for spec in ["anthropic:claude-opus-4-8"]:
        rows, err, cost = run_model(spec, img)
        if err:
            print(f"[{spec}] {err} (cost ${cost:.4f})"); results[spec]=None; continue
        units=rows_to_units(rows)
        m=evaluate(units, gt)
        results[spec]=(rows, units, m)
        print(f"\n=== {spec} (cost ${cost:.4f}) ===")
        print(" rows read:", len(rows or []), "| decoded units:", len(units), "| pred total qty:", sum(u.qty for u in units))
        print(f" group_f1={m.group_f1:.3f} unit_count_error={m.unit_count_error:.3f} "
              f"precision={m.group_precision:.3f} recall={m.group_recall:.3f} "
              f"matched={m.matched_groups} fp={m.fp_groups} fn={m.fn_groups}")
        gate = (m.group_f1>=0.90 and m.unit_count_error<=0.05)
        print(f" GATE {'TAKEN' if gate else 'NOT taken'} (need f1>=0.90 AND uce<=0.05)")
        json.dump({"spec": spec, "gate_taken": bool(gate), "n_units": len(units),
                   "pred_total_qty": sum(u.qty for u in units), "gt_total_qty": gt_total,
                   "thresholds": {"group_f1>=": 0.90, "unit_count_error<=": 0.05},
                   "metrics": {"group_f1": round(m.group_f1, 4),
                               "unit_count_error": round(m.unit_count_error, 4),
                               "precision": round(m.group_precision, 4),
                               "recall": round(m.group_recall, 4),
                               "matched_groups": m.matched_groups,
                               "fp_groups": m.fp_groups, "fn_groups": m.fn_groups}},
                  open("eval/gate_745_result.json", "w"), indent=2)
    # consensus: rows where both models agree on (mark,size_code,qty)
    ok=[(k,v) for k,v in results.items() if v]
    if len(ok)>=2:
        a=ok[0][1]; b=ok[1][1]
        ra={ (str(r.get("mark")).upper(), str(r.get("size_code")).replace(" ",""), int(r.get("qty") or 0)) for r in a[0] }
        rb={ (str(r.get("mark")).upper(), str(r.get("size_code")).replace(" ",""), int(r.get("qty") or 0)) for r in b[0] }
        agree=ra & rb
        tmap={}
        for r in a[0]+b[0]: tmap[(str(r.get("mark")).upper(),str(r.get("size_code")).replace(" ",""))]=str(r.get("type","window"))
        cons_rows=[{"mark":m_,"size_code":s_,"qty":q_,"type":tmap.get((m_,s_),"window")} for (m_,s_,q_) in agree]
        cu=rows_to_units(cons_rows)
        if cu:
            mc=evaluate(cu, gt)
            print(f"\n=== CONSENSUS (both agree, {len(agree)} rows) ===")
            print(f" group_f1={mc.group_f1:.3f} unit_count_error={mc.unit_count_error:.3f} pred_total={sum(u.qty for u in cu)}")
            print(f" GATE {'TAKEN' if (mc.group_f1>=0.90 and mc.unit_count_error<=0.05) else 'NOT taken'}")
    print("\nDONE")


if __name__ == "__main__":
    main()
