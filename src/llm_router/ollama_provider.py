from __future__ import annotations

import os
import json
from typing import List, Dict, Any, Optional
import aiohttp

from .providers import LLMProvider
from ..utils import get_logger

logger = get_logger("ollama_provider")


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: str = "llama3.2",
        timeout: int = 120,
    ):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def name(self) -> str:
        return "ollama"

    async def complete(self, prompt: str, **kwargs) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "")
                    else:
                        logger.error(f"Ollama error: {resp.status}")
                        return ""
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return ""

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("message", {}).get("content", "")
                    else:
                        logger.error(f"Ollama chat error: {resp.status}")
                        return ""
        except Exception as e:
            logger.error(f"Ollama chat request failed: {e}")
            return ""

    async def health_check(self) -> bool:
        url = f"{self.base_url}/api/tags"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception:
            return False
