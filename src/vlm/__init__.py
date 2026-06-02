"""VLM provider registry. Lazy import — only providers with keys load."""
from .base import VLMProvider, VLMResult, MockProvider

__all__ = ["VLMProvider", "VLMResult", "MockProvider", "get_provider"]


def get_provider(spec: str) -> VLMProvider:
    """Spec format: 'anthropic:claude-sonnet-4-6' / 'openai:gpt-4o' /
    'azure:<deployment>' / 'gemini:gemini-2.5-flash' / 'mock'."""
    if spec == "mock":
        return MockProvider(payload=[])
    name, _, model = spec.partition(":")
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=model or "claude-sonnet-4-6")
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(model=model or "gpt-4o")
    if name == "azure":
        from .azure_provider import AzureOpenAIProvider
        return AzureOpenAIProvider(deployment=model or None)
    if name == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(model=model or "gemini-2.5-flash")
    raise ValueError(f"Unknown provider spec: {spec!r}")
