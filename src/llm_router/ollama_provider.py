from __future__ import annotations

from typing import List, Any

from .providers import LLMProvider, Message, LLMResponse


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    @property
    def name(self) -> str:
        return "ollama"

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        return LLMResponse(content=f"Ollama: {prompt}", model="ollama", provider=self.name)

    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="Ollama chat response", model="ollama", provider=self.name)

    async def health_check(self) -> bool:
        return True
