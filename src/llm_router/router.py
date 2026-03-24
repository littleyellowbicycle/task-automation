"""LLM Router for intelligent provider selection."""

from typing import Dict, List, Optional
from .providers import LLMProvider, LLMResponse, Message
from .ollama_provider import OllamaProvider
from .cloud_provider import AnthropicProvider, OpenAIProvider
from ..utils import get_logger
from ..exceptions import LLMRoutingError

logger = get_logger("llm_router")


class LLMRouter:
    """
    LLM Router that intelligently routes requests to appropriate providers.
    
    Supports Ollama (local), Anthropic Claude, and OpenAI GPT.
    Automatically falls back to cloud providers if local provider fails.
    """
    
    def __init__(
        self,
        default_provider: str = "ollama",
        complexity_threshold: str = "medium",
        ollama_config: Optional[dict] = None,
        anthropic_config: Optional[dict] = None,
        openai_config: Optional[dict] = None,
    ):
        """
        Initialize LLM Router.
        
        Args:
            default_provider: Default provider name ("ollama", "anthropic", "openai")
            complexity_threshold: Threshold for complexity ("low", "medium", "high")
            ollama_config: Ollama configuration dict
            anthropic_config: Anthropic configuration dict
            openai_config: OpenAI configuration dict
        """
        self.default_provider = default_provider
        self.complexity_threshold = complexity_threshold
        self._providers: Dict[str, LLMProvider] = {}
        self._init_providers(ollama_config, anthropic_config, openai_config)
    
    def _init_providers(self, ollama_config, anthropic_config, openai_config):
        """Initialize all providers."""
        # Ollama (local)
        if ollama_config:
            self._providers["ollama"] = OllamaProvider(
                base_url=ollama_config.get("base_url", "http://localhost:11434"),
                model=ollama_config.get("model", "llama3.2"),
                timeout=ollama_config.get("timeout", 120),
                stream=ollama_config.get("stream", True),
            )
        
        # Anthropic Claude
        if anthropic_config:
            self._providers["anthropic"] = AnthropicProvider(
                api_key=anthropic_config.get("api_key"),
                model=anthropic_config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=anthropic_config.get("max_tokens", 4096),
            )
        
        # OpenAI GPT
        if openai_config:
            self._providers["openai"] = OpenAIProvider(
                api_key=openai_config.get("api_key"),
                model=openai_config.get("model", "gpt-4o"),
                max_tokens=openai_config.get("max_tokens", 4096),
            )
        
        logger.info(f"Initialized LLM providers: {list(self._providers.keys())}")
    
    @property
    def available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self._providers.keys())
    
    def get_provider(self, name: Optional[str] = None) -> LLMProvider:
        """Get a provider by name."""
        name = name or self.default_provider
        if name not in self._providers:
            raise LLMRoutingError(f"Provider '{name}' not initialized")
        return self._providers[name]
    
    def _assess_complexity(self, prompt: str) -> str:
        """
        Assess the complexity of a task based on the prompt.
        
        Simple heuristics for now - could be enhanced with LLM-based assessment.
        """
        # Check for indicators of complex tasks
        complex_indicators = [
            "analyze", "design", "architect", "complex", "multiple",
            "refactor", "optimize", "implement", "algorithm",
        ]
        
        simple_indicators = [
            "simple", "basic", "quick", "small", "easy",
            "hello", "hi", "test", "example",
        ]
        
        prompt_lower = prompt.lower()
        complex_count = sum(1 for ind in complex_indicators if ind in prompt_lower)
        simple_count = sum(1 for ind in simple_indicators if ind in prompt_lower)
        
        if complex_count > simple_count:
            return "high"
        elif simple_count > complex_count:
            return "low"
        return "medium"
    
    def _should_use_cloud(self, complexity: str) -> bool:
        """Determine if cloud provider should be used based on complexity."""
        threshold_map = {"low": 2, "medium": 1, "high": 0}
        complexity_map = {"low": 0, "medium": 1, "high": 2}
        
        return complexity_map.get(complexity, 1) >= threshold_map.get(self.complexity_threshold, 1)
    
    async def complete(self, prompt: str, provider: Optional[str] = None, **kwargs) -> LLMResponse:
        """
        Generate a completion with automatic provider selection.
        
        Args:
            prompt: The prompt to complete
            provider: Specific provider to use (optional)
            **kwargs: Additional arguments passed to provider
            
        Returns:
            LLMResponse from the selected provider
        """
        if provider:
            return await self.get_provider(provider).complete(prompt, **kwargs)
        
        # Auto-select provider based on complexity
        complexity = kwargs.pop("complexity", self._assess_complexity(prompt))
        
        if self._should_use_cloud(self.default_provider) or self.default_provider == "ollama":
            # Try Ollama first if available
            if "ollama" in self._providers:
                try:
                    ollama = self._providers["ollama"]
                    if await ollama.health_check():
                        logger.debug(f"Using Ollama for task (complexity: {complexity})")
                        return await ollama.complete(prompt, **kwargs)
                except Exception as e:
                    logger.warning(f"Ollama failed, falling back: {e}")
        
        # Fallback to cloud providers
        for cloud_name in ["anthropic", "openai"]:
            if cloud_name in self._providers:
                try:
                    provider = self._providers[cloud_name]
                    if await provider.health_check():
                        logger.debug(f"Using {cloud_name} for task")
                        return await provider.complete(prompt, **kwargs)
                except Exception as e:
                    logger.warning(f"{cloud_name} failed: {e}")
        
        raise LLMRoutingError("No available LLM providers")
    
    async def chat(self, messages: List[Message], provider: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate a chat completion."""
        if provider:
            return await self.get_provider(provider).chat(messages, **kwargs)
        
        # Try providers in order
        for provider_name in self.available_providers:
            try:
                p = self._providers[provider_name]
                if await p.health_check():
                    return await p.chat(messages, **kwargs)
            except Exception as e:
                logger.warning(f"{provider_name} failed: {e}")
        
        raise LLMRoutingError("No available LLM providers for chat")
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for name, provider in self._providers.items():
            results[name] = await provider.health_check()
        return results
    
    async def close(self):
        """Close all provider connections."""
        for provider in self._providers.values():
            await provider.close()
