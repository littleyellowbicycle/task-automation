from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Any


class LLMProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> str:
        ...

    @abstractmethod
    async def chat(self, messages: List[Any], **kwargs) -> str:
        ...

    async def health_check(self) -> bool:
        return True
