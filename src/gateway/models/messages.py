from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class SenderInfo:
    id: str
    name: str
    avatar: Optional[str] = None


@dataclass
class ConversationInfo:
    id: str
    type: str
    name: Optional[str] = None
    member_count: int = 0


@dataclass
class StandardMessage:
    msg_id: str
    platform: str
    listener_type: str
    content: str
    sender: SenderInfo
    conversation: ConversationInfo
    timestamp: datetime
    msg_type: str = "text"
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "platform": self.platform,
            "listener_type": self.listener_type,
            "content": self.content,
            "sender": {
                "id": self.sender.id,
                "name": self.sender.name,
                "avatar": self.sender.avatar,
            },
            "conversation": {
                "id": self.conversation.id,
                "type": self.conversation.type,
                "name": self.conversation.name,
                "member_count": self.conversation.member_count,
            },
            "timestamp": self.timestamp.isoformat(),
            "msg_type": self.msg_type,
        }
