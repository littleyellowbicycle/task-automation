"""LLM Provider base classes and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, AsyncIterator


@dataclass
class Message:
    """Chat message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """LLM response."""
    content: str
    model: str
    provider: str
    usage: Optional[dict] = None
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate a completion for a prompt.
        
        Args:
            prompt: The prompt to complete
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMResponse with the completion
        """
        pass
    
    @abstractmethod
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """
        Generate a chat completion.
        
        Args:
            messages: List of chat messages
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMResponse with the completion
        """
        pass
    
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """
        Stream a completion token by token.
        
        Args:
            prompt: The prompt to complete
            **kwargs: Additional provider-specific arguments
            
        Yields:
            Text chunks as they become available
        """
        response = await self.complete(prompt, **kwargs)
        yield response.content
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    async def close(self):
        """Clean up resources."""
        pass
