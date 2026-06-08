"""Compare GPT-5.5 vs Gemini 3.1 Pro transcripts, render a comparison image,
send rendered A1.0 + comparison to Telegram, save merged GT-pending JSON.
"""
import os, json, base64, time, requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from dotenv import dotenv_values
env = dotenv_values(".env"); os.environ.update({k:v for k,v in env.items() if v})

TG_TOKEN = os.environ.get("TG_BOT_TOKEN","6042040633:AAHhepkyxOzetVsjMroKqWWPe_mEncC70aM")
CHAT    = os.environ.get("TG_CHAT_ID","153749412")

ROOT = Path("runs/r6")
OAI  = json.loads((ROOT/"transcripts/openai_gpt55.json").read_text())["json"]
GEM  = json.loads((ROOT/"transcripts/gemini_31pro.json").read_text())["json"]

# Build merged rows keyed by mark
def index(rows):
    out = {}
    for r in rows:
        k = r.get("#") or r.get("MARK") or r.get("mark")
        if k: out[str(k).strip().upper()] = r
    return out

iOA = index(OAI.get("window_schedule",[]))
iGE = index(GEM.get("window_schedule",[]))
all_marks = sorted(set(list(iOA.keys()) + list(iGE.keys())))

# Columns to compare (canonicalize keys)
KEYS = ["WINDOW SIZE","TYPE","REMARKS","EGRESS","QTY","MANUF.","SERIES","DAY OPEN (SF)","VENT (SF)"]
def get(row, key):
    if not row: return None
    if key in row: return row[key]
    # try alternate punctuations
    for k in row.keys():
        if k.replace(".","").replace(" ","").replace("(SF)","").upper() == key.replace(".","").replace(" ","").replace("(SF)","").upper():
            return row[k]
    # QTY alternates
    if key=="QTY" and "QTY." in row: return row["QTY."]
    return None

# Build comparison rows
rows = []
diffs = 0
for m in all_marks:
    a = iOA.get(m); b = iGE.get(m)
    line = {"mark": m}
    row_diffs = []
    for k in KEYS:
        va, vb = get(a,k), get(b,k)
        match = (va == vb)
        if not match:
            row_diffs.append(k)
        line[k] = {"gpt55": va, "gemini31p": vb, "match": match}
    line["row_diffs"] = row_diffs
    diffs += len(row_diffs)
    rows.append(line)

totals_oa = OAI.get("totals",{})
totals_ge = GEM.get("totals",{})

summary = {
    "marks_present_oa": sorted(iOA.keys()),
    "marks_present_ge": sorted(iGE.keys()),
    "row_count": {"gpt55": len(iOA), "gemini31p": len(iGE)},
    "totals":   {"gpt55": totals_oa, "gemini31p": totals_ge},
    "diff_cells": diffs,
    "door_schedule_present": {
        "gpt55": bool(OAI.get("door_schedule")),
        "gemini31p": bool(GEM.get("door_schedule")),
    },
    "notes": {
        "gpt55": OAI.get("raw_text_note"),
        "gemini31p": GEM.get("raw_text_note"),
    },
}
(ROOT/"transcripts/comparison.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False))
print(json.dumps(summary, indent=2))

# --- Render comparison image (PNG) ---
W,H = 1800, 1500
font_path = None
for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]:
    if os.path.exists(p): font_path = p; break
font   = ImageFont.truetype(font_path, 18) if font_path else ImageFont.load_default()
big    = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default()
small  = ImageFont.truetype(font_path, 14) if font_path else ImageFont.load_default()
im = Image.new("RGB",(W,H),"white")
dr = ImageDraw.Draw(im)
y = 16
dr.text((16,y), "745 Tamarack Trail — sheet A1.0 Window Schedule", fill="black", font=big); y+=34
dr.text((16,y), f"GPT-5.5 vs Gemini 3.1 Pro — diffs: {diffs}", fill="black", font=font); y+=30

# Header
hdrs = ["#"] + KEYS
col_w = [60, 180, 70, 130, 100, 60, 160, 220, 140, 110]
x = 16
for i,h in enumerate(hdrs):
    dr.rectangle([x, y, x+col_w[i], y+26], outline="black", width=1, fill="#eeeeee")
    dr.text((x+4, y+4), h, fill="black", font=small)
    x += col_w[i]
y += 26
# Rows — for each mark, render two sub-rows (gpt55, gem) with highlights
for row in rows:
    m = row["mark"]
    for who in ("gpt55","gemini31p"):
        x = 16
        # mark cell only on first sub-row
        dr.rectangle([x, y, x+col_w[0], y+24], outline="black", width=1, fill="#fafafa")
        if who == "gpt55":
            dr.text((x+4, y+4), m, fill="black", font=small)
        else:
            dr.text((x+4, y+4), "", fill="black", font=small)
        x += col_w[0]
        for i,k in enumerate(KEYS,1):
            cell = row[k]
            val = cell.get(who)
            match = cell["match"]
            fill = "#fff7c2" if not match else "#ffffff"
            dr.rectangle([x, y, x+col_w[i], y+24], outline="black", width=1, fill=fill)
            t = "" if val is None else str(val)
            if len(t)>22: t = t[:22]+"…"
            dr.text((x+4, y+4), t, fill="black", font=small)
            x += col_w[i]
        # Label which model
        dr.text((W-110, y+4), who, fill="#666666", font=small)
        y += 24
    y += 6  # gap between marks
    if y > H-60: break
dr.text((16,H-30), f"Yellow = disagreement between models. Source image: A1.0 (page 1).", fill="black", font=small)
COMP_PNG = ROOT/"transcripts/comparison_745_A10.png"
im.save(COMP_PNG, format="PNG", optimize=True)
print("wrote", COMP_PNG)

# --- Crop schedule region from full-res A1.0 for clarity ---
full = Image.open("runs/r6/renders/p01_300dpi.png")
# schedule typically right portion of sheet — crop right 35% bottom 60%
W_, H_ = full.size
crop = full.crop((int(W_*0.55), int(H_*0.40), W_, H_))
crop.thumbnail((3200, 3200))
SCHED_PNG = ROOT/"transcripts/A10_schedule_crop.png"
if crop.mode != "RGB": crop = crop.convert("RGB")
crop.save(SCHED_PNG, format="JPEG", quality=88)
print("wrote", SCHED_PNG, crop.size)

# Also produce smaller A1.0 full for context
A10_FULL = ROOT/"transcripts/A10_full_2400w.jpg"
full2 = full.copy(); full2.thumbnail((2400,2400))
if full2.mode != "RGB": full2 = full2.convert("RGB")
full2.save(A10_FULL, format="JPEG", quality=88)
print("wrote", A10_FULL)

# --- Send to Telegram ---
def tg_doc(path, caption=""):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    with open(path,"rb") as f:
        r = requests.post(url, data={"chat_id":CHAT, "caption":caption[:1024]}, files={"photo": (os.path.basename(path), f)})
    return r.json()

def tg_msg(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id":CHAT, "text":text[:4000]})
    return r.json()

m1 = tg_msg("R6 STEP 1.4 — PAUSE for human verification.\n"
            "Sending: (1) A1.0 full sheet, (2) schedule region crop, (3) GPT-5.5 vs Gemini 3.1 Pro comparison table.\n"
            "Models AGREE on: 8 marks A-H, 24 units total, all on a single WINDOW SCHEDULE; "
            "no separate DOOR SCHEDULE on this sheet (row D 'TYPE: DR' QTY 2 = patio-door style in window schedule).\n"
            f"Disagreement cells: {diffs}.\n"
            "Please confirm or correct each row before I commit ground_truth/745_extract.json.")
print("tg msg:", m1.get("ok"))
m2 = tg_doc(str(A10_FULL),  "A1.0 full sheet (2400w)")
print("tg full:", m2.get("ok"))
m3 = tg_doc(str(SCHED_PNG), "A1.0 schedule region crop (high-res)")
print("tg crop:", m3.get("ok"))
m4 = tg_doc(str(COMP_PNG),  f"Comparison GPT-5.5 vs Gemini 3.1 Pro — yellow=disagreement, diff cells={diffs}")
print("tg cmp:", m4.get("ok"))
