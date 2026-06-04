"""Anthropic Claude vision."""
from __future__ import annotations
import os
from typing import Any, Dict
from .base import VLMProvider, _img_to_b64


class AnthropicProvider(VLMProvider):
    name = "anthropic"

    PRICE = {  # USD per 1M tokens (approximate, update from console)
        "claude-opus-4-7":  {"in": 15.0, "out": 75.0},
        "claude-opus-4-6":  {"in": 15.0, "out": 75.0},
        "claude-sonnet-4-6":{"in": 3.0,  "out": 15.0},
        "claude-haiku-4-5-20251001": {"in": 0.8, "out": 4.0},
    }

    def __init__(self, model: str = "claude-opus-4-7", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set.")

    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 4096) -> Dict[str, Any]:
        # Lazy import to keep tests light.
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        ext = image_path.lower().rsplit(".", 1)[-1]
        media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
        msg = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": media_type, "data": _img_to_b64(image_path)
                    }},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "text", None))
        in_tok = msg.usage.input_tokens
        out_tok = msg.usage.output_tokens
        price = self.PRICE.get(self.model, {"in": 0.0, "out": 0.0})
        cost = (in_tok / 1e6) * price["in"] + (out_tok / 1e6) * price["out"]
        return {"text": text, "model": self.model, "input_tokens": in_tok,
                "output_tokens": out_tok, "cost_usd": cost}
