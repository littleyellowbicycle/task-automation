"""Tests for LLM router."""

import pytest
from src.llm_router.router import LLMRouter
from src.llm_router.providers import Message


class TestLLMRouter:
    def test_create_router_without_config(self):
        """Router without config should have no providers."""
        router = LLMRouter()
        assert router.default_provider == "ollama"
        assert router.available_providers == []

    def test_create_router_with_config(self):
        """Router with config should initialize providers."""
        router = LLMRouter(
            ollama_config={"base_url": "http://localhost:11434", "model": "llama3.2"}
        )
        assert router.default_provider == "ollama"
        assert "ollama" in router.available_providers

    def test_complexity_assessment(self):
        router = LLMRouter()
        
        # Simple task
        complexity = router._assess_complexity("Hello, how are you?")
        assert complexity == "low"
        
        # Complex task
        complexity = router._assess_complexity("Analyze this code and refactor the architecture")
        assert complexity == "high"

    def test_get_provider_with_config(self):
        router = LLMRouter(
            ollama_config={"base_url": "http://localhost:11434", "model": "llama3.2"}
        )
        provider = router.get_provider("ollama")
        assert provider.name == "ollama"

    def test_get_nonexistent_provider(self):
        router = LLMRouter()
        with pytest.raises(Exception):
            router.get_provider("nonexistent")
