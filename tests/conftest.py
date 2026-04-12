import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from src.wechat_listener.models import WeChatMessage, TaskMessage, MessageType, ConversationType
from src.config.models import AppConfig, WeChatConfig, LLMConfig, FeishuConfig, GatewayConfig


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests as integration tests (require running services)")


def pytest_collection_modifyitems(config, items):
    skip_integration = pytest.mark.skip(reason="integration test - requires running services")

    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def sample_config():
    return AppConfig(
        wechat=WeChatConfig(device_id="test_device"),
        llm=LLMConfig(default_provider="ollama"),
        feishu=FeishuConfig(app_id="test", app_secret="test", table_id="test"),
        gateway=GatewayConfig(host="0.0.0.0", port=8000),
    )


@pytest.fixture
def sample_wechat_message():
    return WeChatMessage(
        msg_id="msg_001",
        msg_type=MessageType.TEXT,
        content="开发一个用户登录功能",
        conversation_id="R:group_001",
        conversation_type=ConversationType.GROUP,
        sender_id="user_001",
        sender_name="Test User",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_task_message(sample_wechat_message):
    return TaskMessage(
        original_message=sample_wechat_message,
        is_project_task=True,
        keywords_matched=["开发"],
        confidence_score=0.8,
    )


@pytest.fixture
def mock_llm_response():
    return {
        "summary": "开发用户登录功能",
        "tech_stack": ["Python", "Flask"],
        "core_features": ["登录", "注册"],
        "complexity": "moderate",
    }
