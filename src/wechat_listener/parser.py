"""Message parser for WeChat listener."""

import re
from typing import List, Optional
from .models import WeChatMessage, TaskMessage, MessageType, ConversationType


class MessageParser:
    """Parser for WeChat messages."""
    
    def __init__(self, keywords: Optional[List[str]] = None, regex_patterns: Optional[List[str]] = None):
        """
        Initialize the message parser.
        
        Args:
            keywords: List of keywords to identify project tasks
            regex_patterns: List of regex patterns to match task messages
        """
        self.keywords = keywords or ["项目发布", "需求", "开发任务", "功能开发", "bug修复", "重构"]
        self.regex_patterns = [
            re.compile(p) for p in (regex_patterns or [
                r"^项目发布[:：]",
                r"^需求[:：]",
                r"^开发[:：]",
            ])
        ]
    
    def parse(self, raw_message: dict) -> WeChatMessage:
        """Parse a raw WeChat message into a WeChatMessage object."""
        msg_type = raw_message.get("msgtype", "text")
        content = raw_message.get("content", "")
        conversation_id = raw_message.get("conversation_id", "")
        
        conversation_type = ConversationType.PRIVATE
        if conversation_id.startswith("R:"):
            conversation_type = ConversationType.GROUP
        
        msg_type_map = {
            "text": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "voice": MessageType.VOICE,
            "video": MessageType.VIDEO,
            "file": MessageType.FILE,
            "link": MessageType.LINK,
        }
        
        return WeChatMessage(
            msg_id=str(raw_message.get("msgid", "")),
            msg_type=msg_type_map.get(msg_type, MessageType.TEXT),
            content=content,
            conversation_id=conversation_id,
            conversation_type=conversation_type,
            sender_id=raw_message.get("sender_id", ""),
            sender_name=raw_message.get("sender_name", "Unknown"),
            raw_data=raw_message,
        )
    
    def is_task_message(self, message: WeChatMessage) -> tuple[bool, List[str]]:
        """Check if a message is a task-related message."""
        if message.msg_type != MessageType.TEXT:
            return False, []
        
        content = message.content.lower()
        matched = []
        
        for keyword in self.keywords:
            if keyword.lower() in content:
                matched.append(keyword)
        
        for pattern in self.regex_patterns:
            if pattern.search(message.content):
                matched.append(pattern.pattern)
        
        return len(matched) > 0, matched
    
    def parse_task_message(self, message: WeChatMessage) -> TaskMessage:
        """Parse a WeChat message into a TaskMessage."""
        is_task, matched = self.is_task_message(message)
        
        return TaskMessage(
            original_message=message,
            is_project_task=is_task,
            keywords_matched=matched,
            confidence_score=len(matched) / max(len(self.keywords), 1),
        )