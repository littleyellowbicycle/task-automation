"""Ollama local LLM provider."""

import httpx
from typing import List, Optional, AsyncIterator
from .providers import LLMProvider, LLMResponse, Message
from ..utils import get_logger
from ..exceptions import LLMConnectionError, LLMTimeoutError

logger = get_logger("ollama_provider")


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2", timeout: int = 120, stream: bool = True):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.stream = stream
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "ollama"
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json={"model": kwargs.get("model", self.model), "prompt": prompt, "stream": False})
                response.raise_for_status()
                data = response.json()
                return LLMResponse(content=data.get("response", ""), model=data.get("model", self.model), provider=self.name)
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama request timed out: {e}")
        except httpx.HTTPError as e:
            raise LLMConnectionError(f"Ollama connection error: {e}")
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json={"model": kwargs.get("model", self.model), "messages": [{"role": m.role, "content": m.content} for m in messages], "stream": False})
                response.raise_for_status()
                data = response.json()
                return LLMResponse(content=data.get("message", {}).get("content", ""), model=data.get("model", self.model), provider=self.name)
        except Exception as e:
            raise LLMConnectionError(f"Ollama chat error: {e}")
    
    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
