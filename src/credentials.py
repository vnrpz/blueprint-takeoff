"""Credentials loader.

Loads API keys from environment variables (or local .env) at first access.
Optional bw CLI integration: if BW_SESSION is set and the key is missing
from env, falls back to `bw get item <name>`.

Values are never logged or repr'd in full.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _load_dotenv() -> None:
    """Lightweight .env loader (no python-dotenv dep at import time)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()


def _bw_get(name: str) -> Optional[str]:
    """Optionally fall back to Bitwarden CLI. Returns None if bw is unavailable."""
    session = os.environ.get("BW_SESSION")
    if not session:
        return None
    try:
        out = subprocess.check_output(
            ["bw", "get", "password", name, "--session", session],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return out.decode().strip() or None
    except Exception:
        return None


class _Secret(str):
    """A str subclass that masks itself in repr but works as a normal string."""
    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        n = len(self)
        if n == 0:
            return "<Secret empty>"
        return f"<Secret len={n} prefix={self[:4]}…>"


def get(key: str, *, bw_name: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Get a credential. Order: env -> bw CLI -> default. Returns masked-repr str."""
    val = os.environ.get(key)
    if not val and bw_name:
        val = _bw_get(bw_name)
    if not val:
        val = default
    return _Secret(val) if val else None


def require(key: str, *, bw_name: Optional[str] = None) -> str:
    v = get(key, bw_name=bw_name)
    if not v:
        raise RuntimeError(
            f"Missing credential {key}. Set it in .env or environment, "
            f"or provide bw item {bw_name!r}."
        )
    return v


@dataclass(frozen=True)
class TGConfig:
    bot_token: str
    chat_id: str

    @classmethod
    def from_env(cls) -> "TGConfig":
        return cls(
            bot_token=require("TG_BOT_TOKEN"),
            chat_id=require("TG_CHAT_ID"),
        )


@dataclass(frozen=True)
class AzureOpenAIConfig:
    endpoint: str
    api_key: str
    deployment: str
    api_version: str

    @classmethod
    def from_env(cls) -> "AzureOpenAIConfig":
        return cls(
            endpoint=require("AZURE_OPENAI_ENDPOINT"),
            api_key=require("AZURE_OPENAI_API_KEY"),
            deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-nano"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        )
