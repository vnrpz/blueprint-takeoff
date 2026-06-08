"""Dual-model transcription of sheet A1.0 from 745 PDF.

Models: gpt-5.5 (OpenAI) + gemini-3.1-pro-preview.
Output JSON: machine-parseable schedule rows.
"""
import os, json, base64, time, traceback
from pathlib import Path
from dotenv import dotenv_values
env = dotenv_values(".env"); os.environ.update({k:v for k,v in env.items() if v})

IMG_FULL = "runs/r6/renders/p01_300dpi.png"
OUT = Path("runs/r6/transcripts")
OUT.mkdir(exist_ok=True, parents=True)

# Downsample to manageable size for both APIs
from PIL import Image
im = Image.open(IMG_FULL)
print("source:", im.size)
MAX_W = 4000
if im.size[0] > MAX_W:
    r = MAX_W/float(im.size[0])
    im = im.resize((MAX_W, int(im.size[1]*r)), Image.LANCZOS)
IMG_SMALL = "runs/r6/renders/p01_a10_4000w.jpg"
if im.mode != "RGB":
    im = im.convert("RGB")
im.save(IMG_SMALL, format="JPEG", quality=92, optimize=True)
print("resampled:", IMG_SMALL, im.size, os.path.getsize(IMG_SMALL)//1024, "KB")

PROMPT = (
    "You are looking at architectural sheet A1.0 from a residential plan set. "
    "It contains a WINDOW SCHEDULE and a DOOR SCHEDULE (separate tables). "
    "Locate BOTH schedule tables on the sheet and transcribe them verbatim. "
    "For each row, extract every cell as drawn in the title block of the table. "
    "If a header column is present, use the header name as the JSON key. "
    "Common columns: mark (e.g. CM1, DR1), rough_opening or RO (width x height), "
    "frame size (width x height), unit size, quantity/QTY, glass (e.g. TEMP, LOW-E, ANN), "
    "egress (Y/N), U-factor / U-value, SHGC, manufacturer, comments. "
    "Output STRICT JSON with this shape and NOTHING ELSE: "
    "{\"window_schedule\": [<row obj>...], \"door_schedule\": [<row obj>...], "
    "\"totals\": {\"windows\": <int|null>, \"doors\": <int|null>, \"all_units\": <int|null>}, "
    "\"raw_text_note\": \"<short note about legibility / occlusions if any>\"}. "
    "Numbers as numbers (inches as floats). If a cell is empty, omit the key. "
    "If a value is ambiguous, prefer the literal text in a key suffixed \"_text\"."
)

def transcribe_openai(img_path: str) -> dict:
    import openai
    cli = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with open(img_path,"rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    t0 = time.time()
    # Try chat.completions vision (GPT-5.5)
    try:
        rsp = cli.chat.completions.create(
            model="gpt-5.5",
            messages=[
                {"role":"system","content":"You transcribe architectural schedule tables exactly as drawn. Reply with JSON only."},
                {"role":"user","content":[
                    {"type":"text","text": PROMPT},
                    {"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{b64}"}}
                ]}
            ],
            response_format={"type":"json_object"},
        )
        text = rsp.choices[0].message.content
        usage = rsp.usage.model_dump() if hasattr(rsp,"usage") and rsp.usage else {}
        return {"ok": True, "model": "gpt-5.5", "elapsed_sec": time.time()-t0, "usage": usage, "json": json.loads(text), "raw": text}
    except Exception as e:
        return {"ok": False, "model": "gpt-5.5", "elapsed_sec": time.time()-t0, "error": str(e)[:500], "tb": traceback.format_exc()[:1500]}

def transcribe_gemini(img_path: str) -> dict:
    import google.generativeai as g
    g.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = g.GenerativeModel("models/gemini-3.1-pro-preview")
    img = Image.open(img_path)
    t0 = time.time()
    try:
        rsp = model.generate_content(
            [PROMPT, img],
            generation_config={"temperature": 0, "response_mime_type":"application/json"},
        )
        text = rsp.text
        usage = {}
        try:
            usage = {"input_tokens": rsp.usage_metadata.prompt_token_count, "output_tokens": rsp.usage_metadata.candidates_token_count}
        except Exception:
            pass
        return {"ok": True, "model": "gemini-3.1-pro-preview", "elapsed_sec": time.time()-t0, "usage": usage, "json": json.loads(text), "raw": text}
    except Exception as e:
        return {"ok": False, "model": "gemini-3.1-pro-preview", "elapsed_sec": time.time()-t0, "error": str(e)[:500], "tb": traceback.format_exc()[:1500]}

print("=== OPENAI ===")
oa = transcribe_openai(IMG_SMALL)
with open(OUT/"openai_gpt55.json","w") as f: json.dump(oa, f, indent=2, ensure_ascii=False)
print("ok=", oa.get("ok"), "elapsed=", oa.get("elapsed_sec"))
if not oa.get("ok"): print("err=", oa.get("error"))

print("=== GEMINI ===")
ge = transcribe_gemini(IMG_SMALL)
with open(OUT/"gemini_31pro.json","w") as f: json.dump(ge, f, indent=2, ensure_ascii=False)
print("ok=", ge.get("ok"), "elapsed=", ge.get("elapsed_sec"))
if not ge.get("ok"): print("err=", ge.get("error"))

print("DONE")
