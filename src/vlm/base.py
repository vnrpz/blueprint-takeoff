"""VLM provider abstraction.

Single interface — extract(image, prompt) -> dict — implemented by Anthropic,
OpenAI, Azure-OpenAI and Gemini concretions. Each pipeline can therefore be
re-run across 2-3 models (TZ §6).
"""
from __future__ import annotations

import abc
import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class VLMResult:
    """Provider-agnostic result. `raw_text` always present; `parsed_json`
    is the best-effort JSON parse from `raw_text`.
    """
    raw_text: str
    parsed_json: Optional[Any] = None
    model: str = ""
    provider: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None


def _img_to_b64(image_path: str | Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _extract_json(text: str) -> Optional[Any]:
    """Strip ```json fences and parse. Returns None if not parseable."""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    candidate = m.group(1) if m else text
    candidate = candidate.strip()
    # If the model returned multiple JSON objects, try array wrap.
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Find first balanced JSON in the text.
    for start_ch, end_ch in (("[", "]"), ("{", "}")):
        i = candidate.find(start_ch)
        if i < 0:
            continue
        depth = 0
        for j in range(i, len(candidate)):
            if candidate[j] == start_ch:
                depth += 1
            elif candidate[j] == end_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[i:j+1])
                    except json.JSONDecodeError:
                        break
    return None


class VLMProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 4096) -> Dict[str, Any]:
        """Provider-specific HTTP call. Returns
        {text, input_tokens, output_tokens, model}."""

    def extract(self, image_path: str | Path, prompt: str, *, max_tokens: int = 4096) -> VLMResult:
        t0 = time.time()
        try:
            resp = self._call(str(image_path), prompt, max_tokens=max_tokens)
        except Exception as e:
            return VLMResult(raw_text="", error=f"{type(e).__name__}: {e}",
                             provider=self.name, latency_ms=int((time.time() - t0) * 1000))
        text = resp.get("text", "")
        return VLMResult(
            raw_text=text,
            parsed_json=_extract_json(text),
            model=resp.get("model", ""),
            provider=self.name,
            cost_usd=resp.get("cost_usd", 0.0),
            latency_ms=int((time.time() - t0) * 1000),
            input_tokens=resp.get("input_tokens", 0),
            output_tokens=resp.get("output_tokens", 0),
        )


class MockProvider(VLMProvider):
    """Deterministic provider for tests — returns canned JSON."""
    name = "mock"

    def __init__(self, payload: Any):
        self._payload = payload

    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 4096) -> Dict[str, Any]:
        return {
            "text": json.dumps(self._payload),
            "model": "mock-1",
            "input_tokens": 100,
            "output_tokens": 200,
            "cost_usd": 0.0,
        }
