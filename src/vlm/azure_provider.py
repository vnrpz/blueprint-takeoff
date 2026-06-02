"""Azure OpenAI vision (deployment-based)."""
from __future__ import annotations
import os
from typing import Any, Dict
from .base import VLMProvider, _img_to_b64


class AzureOpenAIProvider(VLMProvider):
    name = "azure_openai"

    def __init__(
        self,
        deployment: str | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
        api_version: str | None = None,
    ):
        self.deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-nano")
        self.endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
        self.api_version = api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        if not self.endpoint or not self.api_key:
            raise RuntimeError("Azure OpenAI endpoint/key not set.")

    def _call(self, image_path: str, prompt: str, *, max_tokens: int = 4096) -> Dict[str, Any]:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version,
        )
        ext = image_path.lower().rsplit(".", 1)[-1]
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
        data_url = f"data:{mime};base64,{_img_to_b64(image_path)}"
        resp = client.chat.completions.create(
            model=self.deployment,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}],
        )
        text = resp.choices[0].message.content or ""
        u = resp.usage
        return {
            "text": text, "model": f"azure:{self.deployment}",
            "input_tokens": u.prompt_tokens, "output_tokens": u.completion_tokens,
            "cost_usd": 0.0,  # consumption depends on plan; left at 0
        }
