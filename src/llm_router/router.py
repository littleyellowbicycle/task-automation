from __future__ import annotations

import os
from typing import Optional, Dict, List

from .providers import LLMProvider
from .ollama_provider import OllamaProvider
from .cloud_provider import CloudProvider, CloudProviderType
from ..utils import get_logger

logger = get_logger("llm_router")


class LLMResponse:
    def __init__(self, content: str, model: str = "", provider: str = ""):
        self.content = content
        self.model = model
        self.provider = provider


class LLMRouter:
    def __init__(self, providers: Optional[Dict[str, LLMProvider]] = None) -> None:
        self.providers = providers or {}

    def add_provider(self, key: str, provider: LLMProvider) -> None:
        self.providers[key] = provider
        logger.info(f"Added LLM provider: {key}")

    @classmethod
    def create_default(cls) -> "LLMRouter":
        router = cls()
        router.add_provider("ollama", OllamaProvider())

        if os.getenv("ANTHROPIC_API_KEY"):
            router.add_provider("cloud", CloudProvider(CloudProviderType.ANTHROPIC))
        elif os.getenv("OPENAI_API_KEY"):
            router.add_provider("cloud", CloudProvider(CloudProviderType.OPENAI))

        return router

    async def route_task(self, prompt: str, complexity: str = "simple") -> LLMResponse:
        provider_key = "cloud" if complexity == "complex" else "ollama"
        provider = self.providers.get(provider_key)

        if provider is None:
            provider = self.providers.get("ollama") or self.providers.get("cloud")
            provider_key = provider.name if provider else "none"

        if provider is None:
            return LLMResponse("no-provider-available", model="unknown", provider="none")

        try:
            content = await provider.complete(prompt)
            return LLMResponse(content, model=provider.name, provider=provider_key)
        except Exception as e:
            logger.error(f"Provider {provider_key} failed: {e}")
            if provider_key == "ollama" and "cloud" in self.providers:
                logger.info("Falling back to cloud provider")
                cloud = self.providers["cloud"]
                content = await cloud.complete(prompt)
                return LLMResponse(content, model=cloud.name, provider="cloud")

            return LLMResponse(f"error: {e}", model=provider.name, provider=provider_key)

    async def chat(self, messages: List[Dict[str, str]], complexity: str = "simple") -> LLMResponse:
        provider_key = "cloud" if complexity == "complex" else "ollama"
        provider = self.providers.get(provider_key)

        if provider is None:
            provider = self.providers.get("ollama") or self.providers.get("cloud")

        if provider is None:
            return LLMResponse("no-provider-available", model="unknown", provider="none")

        try:
            content = await provider.chat(messages)
            return LLMResponse(content, model=provider.name, provider=provider_key)
        except Exception as e:
            logger.error(f"Chat provider {provider_key} failed: {e}")
            return LLMResponse(f"error: {e}", model=provider.name, provider=provider_key)
