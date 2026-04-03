"""Tests for message parser."""

import pytest
from src.wechat_listener.parser import MessageParser
from src.wechat_listener.models import WeChatMessage, MessageType, ConversationType


class TestMessageParser:
    def test_parse_text_message(self):
        parser = MessageParser()
        raw = {
            "msg_id": "123",
            "msgtype": "text",
            "content": "Hello World",
            "conversation_id": "R:group_001",
            "sender_id": "user_001",
            "sender_name": "Test User",
        }
        msg = parser.parse(raw)
        assert msg.msg_id == "123"
        assert msg.msg_type == MessageType.TEXT
        assert msg.content == "Hello World"

    def test_is_task_message_with_keyword(self):
        parser = MessageParser()
        
        msg = WeChatMessage(
            msg_id="123",
            msg_type=MessageType.TEXT,
            content="项目发布：开发新功能",
            conversation_id="R:group_001",
            conversation_type=ConversationType.GROUP,
            sender_id="user_001",
            sender_name="Test",
        )
        
        task = parser.parse_task_message(msg)
        assert task.is_project_task is True
        assert len(task.keywords_matched) > 0

    def test_is_task_message_without_keyword(self):
        parser = MessageParser()
        
        msg = WeChatMessage(
            msg_id="123",
            msg_type=MessageType.TEXT,
            content="今天天气不错",
            conversation_id="R:group_001",
            conversation_type=ConversationType.GROUP,
            sender_id="user_001",
            sender_name="Test",
        )
        
        task = parser.parse_task_message(msg)
        assert task.is_project_task is False

    def test_parse_task_message(self, sample_wechat_message):
        parser = MessageParser()
        task = parser.parse_task_message(sample_wechat_message)
        assert task.is_project_task is True
