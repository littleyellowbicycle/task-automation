from __future__ import annotations

from typing import Optional

from .ollama_provider import OllamaProvider
from .cloud_provider import CloudProvider
from .providers import LLMProvider, Message, LLMResponse


class LLMRouter:
    def __init__(self, providers: Optional[dict[str, LLMProvider]] = None) -> None:
        self.providers = providers or {
            "ollama": OllamaProvider(),
            "cloud": CloudProvider(),
        }

    def route_task(self, prompt: str, complexity: str = "simple") -> LLMResponse:
        # Route tasks to local Ollama for simple/medium, cloud for complex
        if complexity == "complex":
            provider = self.providers.get("cloud")
        else:
            provider = self.providers.get("ollama")
        if provider is None:
            return LLMResponse(content="no-provider", model="unknown", provider="none")
        # Return placeholder response; real implementation would invoke provider
        return LLMResponse(content=f"Routing to {provider.name} provider", model=getattr(provider, 'name', 'unknown'), provider=provider.name)
