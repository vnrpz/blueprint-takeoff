"""Google Gemini vision (google-generativeai)."""
from __future__ import annotations
import os
from typing import Any, Dict
from .base import VLMProvider


class GeminiProvider(VLMProvider):
    name = "gemini"

    PRICE = {
        "gemini-3.1-pro-preview": {"in": 1.50, "out": 12.0},
        "gemini-3-pro-preview":   {"in": 1.50, "out": 12.0},
        "gemini-pro-latest":      {"in": 1.50, "out": 12.0},
        "gemini-2.5-pro":         {"in": 1.25, "out": 10.0},
        "gemini-2.5-flash":       {"in": 0.075, "out": 0.30},
        "gemini-2.0-flash":       {"in": 0.075, "out": 0.30},
    },
        "gemini-2.5-flash": {"in": 0.075, "out": 0.30},
        "gemini-2.0-flash": {"in": 0.075, "out": 0.30},
    }

    def __init__(self, model: str = "gemini-3.1-pro-preview", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set.")

    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 4096) -> Dict[str, Any]:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        with open(image_path, "rb") as f:
            data = f.read()
        ext = image_path.lower().rsplit(".", 1)[-1]
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
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
