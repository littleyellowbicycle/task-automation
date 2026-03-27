"""Tests for LLM router."""

import pytest
from src.llm_router.router import LLMRouter, LLMResponse
from src.llm_router.providers import LLMProvider
from src.llm_router.ollama_provider import OllamaProvider


class MockProvider(LLMProvider):
    def __init__(self, name: str = "mock"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def complete(self, prompt: str, **kwargs) -> str:
        return f"Mock response to: {prompt}"

    async def chat(self, messages, **kwargs) -> str:
        return "Mock chat response"

    async def health_check(self) -> bool:
        return True


class TestLLMRouter:
    def test_create_router_without_config(self):
        """Router without config should have no providers."""
        router = LLMRouter()
        assert router.providers == {}

    def test_create_router_with_providers(self):
        """Router with config should initialize providers."""
        router = LLMRouter()
        router.add_provider("mock", MockProvider())
        assert "mock" in router.providers

    def test_add_provider(self):
        router = LLMRouter()
        provider = OllamaProvider()
        router.add_provider("ollama", provider)
        assert router.providers["ollama"].name == "ollama"

    def test_response_object(self):
        resp = LLMResponse("test content", model="test", provider="test")
        assert resp.content == "test content"
        assert resp.model == "test"
        assert resp.provider == "test"
