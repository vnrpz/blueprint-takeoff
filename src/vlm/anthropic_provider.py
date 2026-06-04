"""Anthropic Claude vision.

Round 3 hardening:
- Default model = claude-opus-4-8 (newest in /v1/models)
- max_tokens 8192
- Automatic image resize when any dimension > 7680px (Claude vision API
  rejects > 8000px with HTTP 400). Resize keeps aspect ratio.
- Retry on transient errors (5xx, overloaded, rate_limit).
- Raw text always returned in result.raw_text even on partial failures.
"""
from __future__ import annotations

import io
import os
import time
from typing import Any, Dict

from .base import VLMProvider


CLAUDE_VISION_MAX_DIM_PX = 8000
SAFE_DIM_CAP_PX = 7680  # Margin under the Claude cap


def _maybe_resize_to_b64(image_path: str) -> tuple[str, str]:
    """Read image, resize if max-dim > SAFE_DIM_CAP_PX, return (b64_data, media_type)."""
    import base64
    from PIL import Image
    im = Image.open(image_path)
    media_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
    if max(im.size) > SAFE_DIM_CAP_PX:
        # Preserve aspect ratio; cap longest side
        ratio = SAFE_DIM_CAP_PX / float(max(im.size))
        new_size = (int(im.size[0] * ratio), int(im.size[1] * ratio))
        im = im.resize(new_size, Image.LANCZOS)
        # Re-encode (use JPEG to keep payload small if RGB)
        buf = io.BytesIO()
        if im.mode in ("RGBA", "LA"):
            im = im.convert("RGB")
        im.save(buf, format="JPEG", quality=88, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"
    # No resize — re-encode anyway to be safe (handles odd-mode source PNGs)
    if im.mode in ("RGBA", "LA"):
        im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/png"
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii"), media_type


class AnthropicProvider(VLMProvider):
    name = "anthropic"

    PRICE = {  # USD per 1M tokens
        "claude-opus-4-8":  {"in": 15.0, "out": 75.0},
        "claude-opus-4-7":  {"in": 15.0, "out": 75.0},
        "claude-opus-4-6":  {"in": 15.0, "out": 75.0},
        "claude-sonnet-4-6":{"in": 3.0,  "out": 15.0},
        "claude-haiku-4-5-20251001": {"in": 0.8, "out": 4.0},
    }

    _RETRY_STATUS = (429, 500, 502, 503, 504, 529)
    _RETRY_ATTEMPTS = 3

    def __init__(self, model: str = "claude-opus-4-8", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set.")

    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 8192) -> Dict[str, Any]:
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)

        data_b64, media_type = _maybe_resize_to_b64(image_path)

        last_err: Exception | None = None
        for attempt in range(self._RETRY_ATTEMPTS):
            try:
                kwargs = dict(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {
                                "type": "base64", "media_type": media_type, "data": data_b64,
                            }},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                )
                # claude-opus-4-8 deprecated `temperature`; older opus still accepts it
                if not self.model.startswith("claude-opus-4-8"):
                    kwargs["temperature"] = 0
                msg = client.messages.create(**kwargs)
                text = "".join(b.text for b in msg.content if getattr(b, "text", None))
                in_tok = msg.usage.input_tokens
                out_tok = msg.usage.output_tokens
                price = self.PRICE.get(self.model, {"in": 0.0, "out": 0.0})
                cost = (in_tok / 1e6) * price["in"] + (out_tok / 1e6) * price["out"]
                return {"text": text, "model": self.model, "input_tokens": in_tok,
                        "output_tokens": out_tok, "cost_usd": cost,
                        "stop_reason": getattr(msg, "stop_reason", "")}
            except anthropic.APIStatusError as e:
                last_err = e
                if e.status_code in self._RETRY_STATUS and attempt < self._RETRY_ATTEMPTS - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except Exception as e:
                last_err = e
                raise
