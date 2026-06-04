"""OpenAI direct (Chat Completions vision)."""
from __future__ import annotations
import os
from typing import Any, Dict
from .base import VLMProvider, _img_to_b64


class OpenAIProvider(VLMProvider):
    name = "openai"

    PRICE = {
        "gpt-5.5":      {"in": 8.0,  "out": 32.0},
        "gpt-5.5-pro":  {"in": 30.0, "out": 120.0},
        "gpt-5.1":      {"in": 5.0,  "out": 20.0},
        "gpt-5":        {"in": 5.0,  "out": 20.0},
        "gpt-5-pro":    {"in": 25.0, "out": 100.0},
        "gpt-5-mini":   {"in": 0.5,  "out": 2.0},
        "gpt-5-nano":   {"in": 0.1,  "out": 0.4},
        "gpt-4o":       {"in": 2.5,  "out": 10.0},
        "gpt-4o-mini":  {"in": 0.15, "out": 0.6},
        "gpt-4.1":      {"in": 2.0,  "out": 8.0},
        "gpt-4.1-mini": {"in": 0.4,  "out": 1.6},
        "gpt-4.1-nano": {"in": 0.1,  "out": 0.4},
        "o4-mini":      {"in": 1.1,  "out": 4.4},
    }

    _NEW_PARAM_MODELS = ("gpt-5", "o4")

    def __init__(self, model: str = "gpt-5.5", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")

    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 4096) -> Dict[str, Any]:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        ext = image_path.lower().rsplit(".", 1)[-1]
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
        data_url = f"data:{mime};base64,{_img_to_b64(image_path)}"

        kwargs = dict(
            model=self.model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}],
        )
        if any(self.model.startswith(p) for p in self._NEW_PARAM_MODELS):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        resp = client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        in_tok, out_tok = usage.prompt_tokens, usage.completion_tokens
        price = self.PRICE.get(self.model, {"in": 0.0, "out": 0.0})
        cost = (in_tok / 1e6) * price["in"] + (out_tok / 1e6) * price["out"]
        return {"text": text, "model": self.model, "input_tokens": in_tok,
                "output_tokens": out_tok, "cost_usd": cost}
