from __future__ import annotations

import os
from typing import List, Dict, Any, Optional
from enum import Enum

from .providers import LLMProvider
from ..utils import get_logger

logger = get_logger("cloud_provider")


class CloudProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class CloudProvider(LLMProvider):
    def __init__(
        self,
        provider_type: CloudProviderType = CloudProviderType.ANTHROPIC,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        self.provider_type = provider_type
        self.model = model or os.getenv("DEFAULT_CLOUD_MODEL", "claude-sonnet-4-20250514")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.timeout = timeout

    @property
    def name(self) -> str:
        return self.provider_type.value

    async def complete(self, prompt: str, **kwargs) -> str:
        if self.provider_type == CloudProviderType.ANTHROPIC:
            return await self._anthropic_complete(prompt, **kwargs)
        else:
            return await self._openai_complete(prompt, **kwargs)

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        if self.provider_type == CloudProviderType.ANTHROPIC:
            return await self._anthropic_chat(messages, **kwargs)
        else:
            return await self._openai_chat(messages, **kwargs)

    async def _anthropic_complete(self, prompt: str, **kwargs) -> str:
        try:
            import anthropic
        except ImportError:
            logger.error("anthropic package not installed")
            return ""

        client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        try:
            resp = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            return ""

    async def _openai_complete(self, prompt: str, **kwargs) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("openai package not installed")
            return ""

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return ""

    async def _anthropic_chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        try:
            import anthropic
        except ImportError:
            return ""

        client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        try:
            resp = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=messages,
            )
            return resp.content[0].text
        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            return ""

    async def _openai_chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ""

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            return ""

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            test_msg = [{"role": "user", "content": "hi"}]
            result = await self.chat(test_msg)
            return bool(result)
        except Exception:
            return False
