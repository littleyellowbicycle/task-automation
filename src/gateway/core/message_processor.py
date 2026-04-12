from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.messages import SenderInfo, ConversationInfo, StandardMessage
from ...utils import get_logger
from ...exceptions import WeChatAutomationError

logger = get_logger("gateway.message_processor")


class ValidationError(WeChatAutomationError):
    pass


class DuplicateMessageError(WeChatAutomationError):
    pass


@dataclass
class DeduplicationConfig:
    enabled: bool = True
    max_cache_size: int = 1000
    ttl_seconds: int = 3600


class MessageProcessor:
    def __init__(self, dedup_config: Optional[DeduplicationConfig] = None):
        self.dedup_config = dedup_config or DeduplicationConfig()
        self._dedup_cache: Dict[str, float] = {}
        self._dedup_queue: deque = deque()
        self._message_count = 0
        self._duplicate_count = 0
        self._error_count = 0
        self._handler = None

    def register_handler(self, handler) -> None:
        self._handler = handler

    def validate(self, raw_message: Dict[str, Any]) -> bool:
        if not isinstance(raw_message, dict):
            raise ValidationError("Message must be a dictionary")

        if "content" not in raw_message:
            raise ValidationError("Missing required field: content")

        content = raw_message.get("content")
        if not content or not isinstance(content, str):
            raise ValidationError("Content must be a non-empty string")

        return True

    def normalize(
        self,
        raw_message: Dict[str, Any],
        platform: str = "wework",
        listener_type: str = "unknown",
    ) -> StandardMessage:
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

    def is_duplicate(self, msg_id: str) -> bool:
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

    def process(
        self,
        raw_message: Dict[str, Any],
        platform: str = "wework",
        listener_type: str = "unknown",
    ) -> Optional[StandardMessage]:
        self._message_count += 1

        try:
            self.validate(raw_message)
        except ValidationError as e:
            self._error_count += 1
            logger.warning(f"Message validation failed: {e}")
            raise

        message = self.normalize(raw_message, platform, listener_type)

        if self.is_duplicate(message.msg_id):
            self._duplicate_count += 1
            logger.debug(f"Duplicate message detected: {message.msg_id}")
            return None

        return message

    def _generate_msg_id(self, raw_message: Dict[str, Any]) -> str:
        content = raw_message.get("content", "")
        sender_id = raw_message.get("sender_id", "unknown")
        timestamp = raw_message.get("timestamp", time.time())
        unique_str = f"{sender_id}_{content}_{timestamp}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    def _cleanup_expired(self, current_time: float) -> None:
        expired_ids = [
            msg_id for msg_id, ts in self._dedup_cache.items()
            if current_time - ts > self.dedup_config.ttl_seconds
        ]
        for msg_id in expired_ids:
            self._dedup_cache.pop(msg_id, None)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "total_messages": self._message_count,
            "duplicates": self._duplicate_count,
            "errors": self._error_count,
            "processed": self._message_count - self._duplicate_count - self._error_count,
            "cache_size": len(self._dedup_cache),
        }
