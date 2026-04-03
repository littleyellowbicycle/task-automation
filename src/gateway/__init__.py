"""Message Gateway module for message validation, normalization and dispatch."""

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("gateway")


class GatewayError(WeChatAutomationError):
    """Base exception for gateway errors."""
    pass


class ValidationError(GatewayError):
    """Raised when message validation fails."""
    pass


class DuplicateMessageError(GatewayError):
    """Raised when a duplicate message is detected."""
    pass


@dataclass
class SenderInfo:
    """Information about the message sender."""
    id: str
    name: str
    avatar: Optional[str] = None


@dataclass
class ConversationInfo:
    """Information about the conversation."""
    id: str
    type: str  # "private" or "group"
    name: Optional[str] = None
    member_count: int = 0


@dataclass
class StandardMessage:
    """Standardized message structure."""
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


@dataclass
class DeduplicationConfig:
    """Configuration for message deduplication."""
    enabled: bool = True
    max_cache_size: int = 1000
    ttl_seconds: int = 3600  # 1 hour


class MessageGateway:
    """
    Message Gateway for validation, normalization, and dispatch.
    
    Responsibilities:
    - Validate incoming messages
    - Normalize to StandardMessage format
    - Deduplicate messages
    - Dispatch to registered handlers
    """
    
    REQUIRED_FIELDS = ["content"]
    OPTIONAL_FIELDS = [
        "msg_id", "sender_id", "sender_name", "conversation_id",
        "conversation_type", "timestamp", "msg_type", "platform"
    ]
    
    def __init__(
        self,
        dedup_config: Optional[DeduplicationConfig] = None,
        validators: Optional[List[Callable[[dict], bool]]] = None,
    ):
        self.dedup_config = dedup_config or DeduplicationConfig()
        self.validators = validators or []
        self._handlers: List[Callable[[StandardMessage], None]] = []
        self._dedup_cache: Dict[str, float] = {}
        self._dedup_queue: deque = deque()
        self._message_count = 0
        self._duplicate_count = 0
        self._error_count = 0
    
    def register_handler(self, handler: Callable[[StandardMessage], None]) -> None:
        """Register a message handler."""
        self._handlers.append(handler)
        logger.info(f"Registered handler: {handler.__name__ if hasattr(handler, '__name__') else handler}")
    
    def unregister_handler(self, handler: Callable[[StandardMessage], None]) -> None:
        """Unregister a message handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)
            logger.info(f"Unregistered handler: {handler}")
    
    def validate(self, raw_message: Dict[str, Any]) -> bool:
        """
        Validate raw message data.
        
        Args:
            raw_message: Raw message dictionary
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(raw_message, dict):
            raise ValidationError("Message must be a dictionary")
        
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in raw_message:
                raise ValidationError(f"Missing required field: {field_name}")
        
        content = raw_message.get("content")
        if not content or not isinstance(content, str):
            raise ValidationError("Content must be a non-empty string")
        
        for validator in self.validators:
            if not validator(raw_message):
                raise ValidationError("Custom validation failed")
        
        return True
    
    def _generate_msg_id(self, raw_message: Dict[str, Any]) -> str:
        """Generate a unique message ID."""
        content = raw_message.get("content", "")
        sender_id = raw_message.get("sender_id", "unknown")
        timestamp = raw_message.get("timestamp", time.time())
        
        unique_str = f"{sender_id}_{content}_{timestamp}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    def _is_duplicate(self, msg_id: str) -> bool:
        """Check if message is a duplicate."""
        if not self.dedup_config.enabled:
            return False
        
        current_time = time.time()
        
        if msg_id in self._dedup_cache:
            cached_time = self._dedup_cache[msg_id]
            if current_time - cached_time < self.dedup_config.ttl_seconds:
                return True
        
        self._dedup_cache[msg_id] = current_time
        self._dedup_queue.append(msg_id)
        
        while len(self._dedup_queue) > self.dedup_config.max_cache_size:
            old_id = self._dedup_queue.popleft()
            self._dedup_cache.pop(old_id, None)
        
        self._cleanup_expired(current_time)
        
        return False
    
    def _cleanup_expired(self, current_time: float) -> None:
        """Clean up expired entries from dedup cache."""
        expired_ids = [
            msg_id for msg_id, timestamp in self._dedup_cache.items()
            if current_time - timestamp > self.dedup_config.ttl_seconds
        ]
        
        for msg_id in expired_ids:
            self._dedup_cache.pop(msg_id, None)
    
    def normalize(
        self,
        raw_message: Dict[str, Any],
        platform: str = "wework",
        listener_type: str = "unknown",
    ) -> StandardMessage:
        """
        Normalize raw message to StandardMessage.
        
        Args:
            raw_message: Raw message dictionary
            platform: Source platform (wework/wechat)
            listener_type: Type of listener that received the message
            
        Returns:
            Standardized message
        """
        msg_id = raw_message.get("msg_id") or self._generate_msg_id(raw_message)
        
        sender = SenderInfo(
            id=raw_message.get("sender_id", "unknown"),
            name=raw_message.get("sender_name", "unknown"),
            avatar=raw_message.get("sender_avatar"),
        )
        
        conversation_type = raw_message.get("conversation_type", "private")
        is_group = conversation_type in ("group", "GROUP") or (
            isinstance(conversation_type, str) and conversation_type.startswith("R:")
        )
        
        conversation = ConversationInfo(
            id=raw_message.get("conversation_id", "unknown"),
            type="group" if is_group else "private",
            name=raw_message.get("conversation_name"),
            member_count=raw_message.get("member_count", 0),
        )
        
        timestamp_raw = raw_message.get("timestamp")
        if isinstance(timestamp_raw, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp_raw, tz=timezone.utc)
        elif isinstance(timestamp_raw, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_raw)
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        elif isinstance(timestamp_raw, datetime):
            timestamp = timestamp_raw
        else:
            timestamp = datetime.now(timezone.utc)
        
        return StandardMessage(
            msg_id=msg_id,
            platform=platform,
            listener_type=listener_type,
            content=raw_message.get("content", ""),
            sender=sender,
            conversation=conversation,
            timestamp=timestamp,
            msg_type=raw_message.get("msg_type", "text"),
            raw_data=raw_message,
        )
    
    def process(
        self,
        raw_message: Dict[str, Any],
        platform: str = "wework",
        listener_type: str = "unknown",
    ) -> Optional[StandardMessage]:
        """
        Process a raw message through the gateway.
        
        Args:
            raw_message: Raw message dictionary
            platform: Source platform
            listener_type: Type of listener
            
        Returns:
            StandardMessage if processed successfully, None if duplicate
        """
        self._message_count += 1
        
        try:
            self.validate(raw_message)
        except ValidationError as e:
            self._error_count += 1
            logger.warning(f"Message validation failed: {e}")
            raise
        
        message = self.normalize(raw_message, platform, listener_type)
        
        if self._is_duplicate(message.msg_id):
            self._duplicate_count += 1
            logger.debug(f"Duplicate message detected: {message.msg_id}")
            return None
        
        self._dispatch(message)
        
        return message
    
    def _dispatch(self, message: StandardMessage) -> None:
        """Dispatch message to all registered handlers."""
        for handler in self._handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Handler {handler.__name__ if hasattr(handler, '__name__') else handler} failed: {e}")
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get gateway statistics."""
        return {
            "total_messages": self._message_count,
            "duplicates": self._duplicate_count,
            "errors": self._error_count,
            "processed": self._message_count - self._duplicate_count - self._error_count,
            "cache_size": len(self._dedup_cache),
            "handler_count": len(self._handlers),
        }
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._message_count = 0
        self._duplicate_count = 0
        self._error_count = 0
