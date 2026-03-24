from __future__ import annotations

from typing import List, Any

from .providers import LLMProvider, Message, LLMResponse


class CloudProvider(LLMProvider):
    def __init__(self, api_key: str = "", model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model

    @property
    def name(self) -> str:
        return "cloud"

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        return LLMResponse(content=f"Cloud({self.model}) response: {prompt}", model=self.model, provider=self.name)

    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="Cloud chat response", model=self.model, provider=self.name)

    async def health_check(self) -> bool:
        return True
