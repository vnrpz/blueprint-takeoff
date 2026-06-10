import os, json
from dotenv import dotenv_values
env = dotenv_values(".env"); os.environ.update({k:v for k,v in env.items() if v})
import google.generativeai as g
g.configure(api_key=os.environ["GEMINI_API_KEY"])
from PIL import Image
model = g.GenerativeModel("models/gemini-3.1-pro-preview")
results = []
for i in range(1,16):
    p = f"runs/r6/thumbs/p{i:02d}.png"
    img = Image.open(p)
    prompt = (
        "This is a thumbnail of one sheet from an architectural plan PDF. "
        "Answer ONLY a JSON object on one line with keys: "
        "sheet_number (as written in title block, e.g. A1.0), "
        "title (sheet title), "
        "contains_window_or_door_schedule (true|false). "
        "If a sheet contains a tabular Window/Door Schedule with marks like CM1, CM2, DR1, DR2 set the boolean to true."
    )
    try:
        r = model.generate_content([prompt, img], generation_config={"temperature":0})
        text = r.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n",1)[1] if "\n" in text else text
            text = text.rsplit("```",1)[0]
        try:
            obj = json.loads(text)
        except Exception:
            obj = {"raw": text}
        obj["p"] = i
    except Exception as e:
        obj = {"p": i, "error": str(e)[:200]}
    results.append(obj)
    print(json.dumps(obj, ensure_ascii=False))

with open("runs/r6/sheet_id.json","w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("=== SCHEDULE CANDIDATES ===")
for r in results:
    if r.get("contains_window_or_door_schedule"):
        print(" *", r)
