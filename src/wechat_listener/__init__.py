"""WeChat listener module with multiple implementation support."""

from .base import BaseListener, ListenerType, Platform, MessageCallback
from .factory import ListenerFactory
from .parser import MessageParser
from .models import WeChatMessage, TaskMessage, MessageType, ConversationType

from .listeners import NtWorkListener, WebhookListener, UIAutomationListener

__all__ = [
    "BaseListener",
    "ListenerType",
    "Platform",
    "MessageCallback",
    "ListenerFactory",
    "MessageParser",
    "WeChatMessage",
    "TaskMessage",
    "MessageType",
    "ConversationType",
    "NtWorkListener",
    "WebhookListener",
    "UIAutomationListener",
]
