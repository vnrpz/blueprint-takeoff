"""Google Gemini vision (google-generativeai).

R4 hardening:
- Pre-resize PNG to ≤ 5000 px longest side (mitigates DeadlineExceeded
  504 on D-size 300 DPI blueprints).
- Retry 3x with exponential backoff on transient errors (DeadlineExceeded,
  ResourceExhausted, 503/504).
- temperature=0.
"""
from __future__ import annotations

import io
import os
import time
from typing import Any, Dict

from .base import VLMProvider


GEMINI_SAFE_DIM_PX = 5000


def _maybe_resize_to_bytes(image_path: str) -> tuple[bytes, str]:
    """Load PNG, resize if needed, return (raw_bytes, mime)."""
    from PIL import Image
    im = Image.open(image_path)
    if max(im.size) > GEMINI_SAFE_DIM_PX:
        ratio = GEMINI_SAFE_DIM_PX / float(max(im.size))
        new_size = (int(im.size[0] * ratio), int(im.size[1] * ratio))
        im = im.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        if im.mode in ("RGBA", "LA"):
            im = im.convert("RGB")
        im.save(buf, format="JPEG", quality=88, optimize=True)
        return buf.getvalue(), "image/jpeg"
    with open(image_path, "rb") as f:
        return f.read(), "image/png" if image_path.lower().endswith(".png") else "image/jpeg"


class GeminiProvider(VLMProvider):
    name = "gemini"

    PRICE = {
        "gemini-3.1-pro-preview": {"in": 1.50, "out": 12.0},
        "gemini-3-pro-preview":   {"in": 1.50, "out": 12.0},
        "gemini-pro-latest":      {"in": 1.50, "out": 12.0},
        "gemini-2.5-pro":         {"in": 1.25, "out": 10.0},
        "gemini-2.5-flash":       {"in": 0.075, "out": 0.30},
        "gemini-2.0-flash":       {"in": 0.075, "out": 0.30},
    }

    _RETRY_ATTEMPTS = 3

    def __init__(self, model: str = "gemini-3.1-pro-preview", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set.")

    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 8192) -> Dict[str, Any]:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        data, mime = _maybe_resize_to_bytes(image_path)

        last_err = None
        for attempt in range(self._RETRY_ATTEMPTS):
            try:
                resp = model.generate_content(
                    [{"mime_type": mime, "data": data}, prompt],
                    generation_config={"max_output_tokens": max_tokens, "temperature": 0},
                )
                text = resp.text or ""
                try:
                    in_tok = resp.usage_metadata.prompt_token_count
                    out_tok = resp.usage_metadata.candidates_token_count
                except Exception:
                    in_tok, out_tok = 0, 0
                price = self.PRICE.get(self.model, {"in": 0.0, "out": 0.0})
                cost = (in_tok / 1e6) * price["in"] + (out_tok / 1e6) * price["out"]
                return {"text": text, "model": self.model, "input_tokens": in_tok,
                        "output_tokens": out_tok, "cost_usd": cost}
            except Exception as e:
                msg = str(e)
                last_err = e
                if any(t in msg for t in ("Deadline", "504", "503", "ResourceExhausted", "429")):
                    if attempt < self._RETRY_ATTEMPTS - 1:
                        time.sleep(2 ** attempt)
                        continue
                raise
