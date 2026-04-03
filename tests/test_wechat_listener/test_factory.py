"""Tests for the listener factory and base classes."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.wechat_listener import (
    BaseListener,
    ListenerType,
    Platform,
    MessageCallback,
    ListenerFactory,
    NtWorkListener,
    WebhookListener,
    UIAutomationListener,
)
from src.wechat_listener.models import WeChatMessage, TaskMessage, MessageType, ConversationType


class TestListenerType:
    def test_listener_type_values(self):
        assert ListenerType.NTWORK.value == "ntwork"
        assert ListenerType.WEBHOOK.value == "webhook"
        assert ListenerType.UIAUTOMATION.value == "uiautomation"


class TestPlatform:
    def test_platform_values(self):
        assert Platform.WEWORK.value == "wework"
        assert Platform.WECHAT.value == "wechat"


class TestMessageCallback:
    def test_callback_creation(self):
        on_msg = Mock()
        on_task = Mock()
        on_err = Mock()
        
        callback = MessageCallback(
            on_message=on_msg,
            on_task_message=on_task,
            on_error=on_err,
        )
        
        assert callback.on_message == on_msg
        assert callback.on_task_message == on_task
        assert callback.on_error == on_err
    
    def test_callback_defaults(self):
        callback = MessageCallback()
        assert callback.on_message is None
        assert callback.on_task_message is None
        assert callback.on_error is None


class TestListenerFactory:
    def test_create_uiautomation_listener(self):
        listener = ListenerFactory.create(
            listener_type=ListenerType.UIAUTOMATION,
            platform=Platform.WEWORK,
        )
        assert isinstance(listener, UIAutomationListener)
        assert listener.listener_type == ListenerType.UIAUTOMATION
        assert listener.platform == Platform.WEWORK
    
    def test_create_webhook_listener(self):
        listener = ListenerFactory.create(
            listener_type=ListenerType.WEBHOOK,
            platform=Platform.WECHAT,
            host="127.0.0.1",
            port=9000,
        )
        assert isinstance(listener, WebhookListener)
        assert listener.listener_type == ListenerType.WEBHOOK
        assert listener.platform == Platform.WECHAT
        assert listener.host == "127.0.0.1"
        assert listener.port == 9000
    
    @patch("src.wechat_listener.listeners.network_listener.NTWORK_AVAILABLE", True)
    def test_create_ntwork_listener(self):
        listener = ListenerFactory.create(
            listener_type=ListenerType.NTWORK,
            platform=Platform.WEWORK,
            device_id="test_device",
        )
        assert isinstance(listener, NtWorkListener)
        assert listener.listener_type == ListenerType.NTWORK
        assert listener.device_id == "test_device"
    
    def test_create_from_config(self):
        config = {
            "listener_type": "uiautomation",
            "platform": "wework",
            "keywords": ["项目发布"],
            "uiautomation": {
                "poll_interval": 1.0,
                "max_history": 50,
            },
        }
        
        listener = ListenerFactory.create_from_config(config)
        assert isinstance(listener, UIAutomationListener)
        assert listener.poll_interval == 1.0
        assert listener.max_history == 50
        assert listener.keywords == ["项目发布"]
    
    def test_create_from_config_invalid_type(self):
        config = {
            "listener_type": "invalid",
        }
        
        with pytest.raises(Exception):
            ListenerFactory.create_from_config(config)
    
    def test_available_types(self):
        types = ListenerFactory.available_types()
        assert "ntwork" in types
        assert "webhook" in types
        assert "uiautomation" in types
    
    def test_available_platforms(self):
        platforms = ListenerFactory.available_platforms()
        assert "wework" in platforms
        assert "wechat" in platforms


class TestUIAutomationListener:
    def test_init(self):
        listener = UIAutomationListener(
            platform=Platform.WEWORK,
            poll_interval=0.3,
            max_history=50,
            keywords=["测试"],
        )
        
        assert listener.platform == Platform.WEWORK
        assert listener.poll_interval == 0.3
        assert listener.max_history == 50
        assert listener.keywords == ["测试"]
        assert listener.listener_type == ListenerType.UIAUTOMATION
    
    def test_is_running_default(self):
        listener = UIAutomationListener()
        assert listener.is_running is False
    
    def test_set_callback(self):
        listener = UIAutomationListener()
        callback = MessageCallback(on_message=Mock())
        
        listener.set_callback(callback)
        assert listener._callback == callback
    
    def test_get_contacts_without_window(self):
        listener = UIAutomationListener()
        contacts = listener.get_contacts()
        assert contacts == []
    
    def test_get_rooms_without_window(self):
        listener = UIAutomationListener()
        rooms = listener.get_rooms()
        assert rooms == []
    
    def test_send_text_without_window(self):
        listener = UIAutomationListener()
        result = listener.send_text("test_id", "test message")
        assert result is False


class TestWebhookListener:
    def test_init(self):
        listener = WebhookListener(
            platform=Platform.WECHAT,
            host="127.0.0.1",
            port=9000,
            token="test_token",
        )
        
        assert listener.platform == Platform.WECHAT
        assert listener.host == "127.0.0.1"
        assert listener.port == 9000
        assert listener.token == "test_token"
        assert listener.listener_type == ListenerType.WEBHOOK
    
    def test_send_text_not_supported(self):
        listener = WebhookListener()
        result = listener.send_text("test_id", "test message")
        assert result is False


class TestNtWorkListener:
    @patch("src.wechat_listener.listeners.network_listener.NTWORK_AVAILABLE", False)
    def test_init_without_ntwork(self):
        listener = NtWorkListener()
        assert listener.listener_type == ListenerType.NTWORK
    
    @patch("src.wechat_listener.listeners.network_listener.NTWORK_AVAILABLE", False)
    def test_connect_without_ntwork_raises(self):
        import asyncio
        listener = NtWorkListener()
        
        with pytest.raises(Exception) as exc_info:
            asyncio.run(listener.connect())
        
        assert "ntwork is not installed" in str(exc_info.value)


class TestWeChatMessage:
    def test_message_creation(self):
        msg = WeChatMessage(
            msg_id="test_123",
            msg_type=MessageType.TEXT,
            content="测试消息",
            conversation_id="conv_1",
            conversation_type=ConversationType.GROUP,
            sender_id="user_1",
            sender_name="测试用户",
            platform=Platform.WEWORK,
        )
        
        assert msg.msg_id == "test_123"
        assert msg.msg_type == MessageType.TEXT
        assert msg.content == "测试消息"
        assert msg.is_group_message is True
        assert msg.is_private_message is False
        assert msg.platform == Platform.WEWORK
    
    def test_message_platform_default(self):
        msg = WeChatMessage(
            msg_id="test",
            msg_type=MessageType.TEXT,
            content="test",
            conversation_id="conv",
            conversation_type=ConversationType.PRIVATE,
            sender_id="user",
            sender_name="user",
        )
        
        assert msg.platform == Platform.WEWORK


class TestTaskMessage:
    def test_task_message_creation(self):
        original = WeChatMessage(
            msg_id="test",
            msg_type=MessageType.TEXT,
            content="项目发布：新功能",
            conversation_id="conv",
            conversation_type=ConversationType.GROUP,
            sender_id="user",
            sender_name="user",
        )
        
        task = TaskMessage(
            original_message=original,
            is_project_task=True,
            keywords_matched=["项目发布"],
            confidence_score=0.9,
        )
        
        assert task.is_project_task is True
        assert task.keywords_matched == ["项目发布"]
        assert task.confidence_score == 0.9
        assert task.raw_text == "项目发布：新功能"
