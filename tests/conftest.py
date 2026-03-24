"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.models import AppConfig, WeChatConfig, LLMConfig, FeishuConfig
from src.wechat_listener.models import WeChatMessage, MessageType, ConversationType, TaskMessage


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return AppConfig(
        wechat=WeChatConfig(device_id="test_device"),
        llm=LLMConfig(default_provider="ollama"),
        feishu=FeishuConfig(app_id="test_app", app_secret="test_secret"),
    )


@pytest.fixture
def sample_wechat_message():
    """Sample WeChat message for testing."""
    from datetime import datetime
    return WeChatMessage(
        msg_id="test_001",
        msg_type=MessageType.TEXT,
        content="项目发布：测试任务",
        conversation_id="R:group_001",
        conversation_type=ConversationType.GROUP,
        sender_id="user_001",
        sender_name="Test User",
        timestamp=datetime.now(),
    )


@pytest.fixture
def sample_task_message(sample_wechat_message):
    """Sample task message for testing."""
    return TaskMessage(
        original_message=sample_wechat_message,
        is_project_task=True,
        keywords_matched=["项目发布"],
        confidence_score=0.8,
    )


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    return {
        "summary": "测试摘要",
        "tech_stack": ["Python", "Flask"],
        "core_features": ["用户登录", "验证码"],
        "constraints": [],
        "estimated_complexity": "medium"
    }
