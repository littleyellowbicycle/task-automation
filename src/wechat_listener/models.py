"""Message models for WeChat listener."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class MessageType(str, Enum):
    """WeChat message types."""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    LINK = "link"
    LOCATION = "location"
    CARD = "card"
    SYSTEM = "system"


class ConversationType(str, Enum):
    """Conversation types."""
    PRIVATE = "private"
    GROUP = "group"


class Platform(str, Enum):
    """Supported chat platforms."""
    WEWORK = "wework"
    WECHAT = "wechat"


@dataclass
class WeChatMessage:
    """Represents a WeChat message."""
    msg_id: str
    msg_type: MessageType
    content: str
    conversation_id: str
    conversation_type: ConversationType
    sender_id: str
    sender_name: str
    platform: Platform = Platform.WEWORK
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Optional[Dict[str, Any]] = None
    
    @property
    def is_group_message(self) -> bool:
        """Check if this is a group message."""
        return self.conversation_type == ConversationType.GROUP
    
    @property
    def is_private_message(self) -> bool:
        """Check if this is a private message."""
        return self.conversation_type == ConversationType.PRIVATE


@dataclass
class TaskMessage:
    """A message that has been identified as a task."""
    original_message: WeChatMessage
    is_project_task: bool = False
    keywords_matched: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    @property
    def raw_text(self) -> str:
        """Get the raw text content."""
        return self.original_message.content
