"""Tests for WeChat listener models."""

import pytest
from datetime import datetime
from src.wechat_listener.models import (
    WeChatMessage, TaskMessage, MessageType, ConversationType
)


class TestWeChatMessage:
    def test_create_message(self):
        msg = WeChatMessage(
            msg_id="123",
            msg_type=MessageType.TEXT,
            content="Hello",
            conversation_id="R:group_001",
            conversation_type=ConversationType.GROUP,
            sender_id="user_001",
            sender_name="Test",
        )
        assert msg.msg_id == "123"
        assert msg.msg_type == MessageType.TEXT
        assert msg.is_group_message is True
        assert msg.is_private_message is False

    def test_private_message(self):
        msg = WeChatMessage(
            msg_id="456",
            msg_type=MessageType.TEXT,
            content="Private",
            conversation_id="P:user_002",
            conversation_type=ConversationType.PRIVATE,
            sender_id="user_002",
            sender_name="Private User",
        )
        assert msg.is_group_message is False
        assert msg.is_private_message is True


class TestTaskMessage:
    def test_create_task_message(self, sample_wechat_message):
        task = TaskMessage(
            original_message=sample_wechat_message,
            is_project_task=True,
            keywords_matched=["项目发布"],
            confidence_score=0.8,
        )
        assert task.is_project_task is True
        assert "项目发布" in task.keywords_matched
        assert task.raw_text == sample_wechat_message.content
