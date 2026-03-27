from __future__ import annotations

from typing import Dict, Any
from datetime import datetime

from .models import WeChatMessage, MessageType, ConversationType, TaskMessage


class MessageParser:
    """Lightweight parser to convert raw webhook data into WeChat events."""

    def __init__(self, keywords: list[str] | None = None, regex_patterns: list[str] | None = None):
        self.keywords = keywords or ["项目发布", "需求", "开发任务"]
        self.regex_patterns = regex_patterns or []

    def parse(self, payload: Dict[str, Any]) -> WeChatMessage:
        content = payload.get("content") or payload.get("text") or payload.get("message", "")
        msg_type = MessageType.TEXT if isinstance(content, str) else MessageType.TEXT
        conversation_id = payload.get("conversation_id", "C:unknown")
        sender_id = payload.get("sender_id", payload.get("from", "unknown"))
        is_group = payload.get("conversation_type", "group") in ("group", "GROUP")
        conv_type = ConversationType.GROUP if is_group else ConversationType.PRIVATE

        msg_id = str(payload.get("msgid") or payload.get("msg_id") or id(payload))
        
        wm = WeChatMessage(
            msg_id=msg_id,
            msg_type=msg_type,
            content=str(content),
            conversation_id=conversation_id,
            conversation_type=conv_type,
            sender_id=sender_id,
            sender_name=payload.get("sender_name", "unknown"),
            timestamp=datetime.utcnow(),
            raw_data=payload,
        )
        return wm

    def is_task_message(self, wechat_message: WeChatMessage) -> tuple[bool, list[str]]:
        """Check if message is a task and return matched keywords."""
        text = wechat_message.content.lower() if wechat_message.content else ""
        matched = [kw for kw in self.keywords if kw in text]
        is_task = any(m in text for m in ["project", "需求", "开发"])
        return bool(is_task or matched), matched

    def parse_task_message(self, wechat_message: WeChatMessage) -> TaskMessage:
        text = wechat_message.content.lower() if wechat_message.content else ""
        matched = [kw for kw in self.keywords if kw in text]
        is_task = any(m in text for m in ["project", "需求", "开发"])
        tm = TaskMessage(
            original_message=wechat_message,
            is_project_task=bool(is_task or matched),
            keywords_matched=matched,
            confidence_score=0.8 if is_task or matched else 0.0,
        )
        return tm
