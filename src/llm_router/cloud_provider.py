"""Cloud LLM providers (Anthropic Claude, OpenAI)."""

import os
from typing import List, Optional
from .providers import LLMProvider, LLMResponse, Message
from ..utils import get_logger
from ..exceptions import LLMConnectionError, LLMTimeoutError

logger = get_logger("cloud_provider")


class AnthropicProvider(LLMProvider):
    """Anthropic Claude cloud provider."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ):
        """
        Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate completion using Claude."""
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.api_key)
            
            response = await client.messages.create(
                model=kwargs.get("model", self.model),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                messages=[{"role": "user", "content": prompt}]
            )
            
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                provider=self.name,
                usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
                finish_reason=response.stop_reason,
            )
        except Exception as e:
            raise LLMConnectionError(f"Anthropic API error: {e}")
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """Generate chat completion using Claude."""
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.api_key)
            
            response = await client.messages.create(
                model=kwargs.get("model", self.model),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                messages=[{"role": m.role, "content": m.content} for m in messages]
            )
            
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                provider=self.name,
                usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
                finish_reason=response.stop_reason,
            )
        except Exception as e:
            raise LLMConnectionError(f"Anthropic API error: {e}")
    
    async def health_check(self) -> bool:
        """Check if Anthropic API is accessible."""
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.api_key)
            await client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            logger.debug(f"Anthropic health check failed: {e}")
            return False


class OpenAIProvider(LLMProvider):
    """OpenAI GPT cloud provider."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
    
    @property
    def name(self) -> str:
        return "openai"
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate completion using GPT."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            
            response = await client.chat.completions.create(
                model=kwargs.get("model", self.model),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                messages=[{"role": "user", "content": prompt}]
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                provider=self.name,
                usage={"prompt_tokens": response.usage.prompt_tokens, "completion_tokens": response.usage.completion_tokens},
                finish_reason=response.choices[0].finish_reason,
            )
        except Exception as e:
            raise LLMConnectionError(f"OpenAI API error: {e}")
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """Generate chat completion using GPT."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            
            response = await client.chat.completions.create(
                model=kwargs.get("model", self.model),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                messages=[{"role": m.role, "content": m.content} for m in messages]
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                provider=self.name,
                usage={"prompt_tokens": response.usage.prompt_tokens, "completion_tokens": response.usage.completion_tokens},
                finish_reason=response.choices[0].finish_reason,
            )
        except Exception as e:
            raise LLMConnectionError(f"OpenAI API error: {e}")
    
    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            await client.chat.completions.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            logger.debug(f"OpenAI health check failed: {e}")
            return False
