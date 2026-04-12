import pytest
from datetime import datetime, timezone

from src.gateway.core.message_processor import MessageProcessor, ValidationError
from src.gateway.models.messages import StandardMessage, SenderInfo, ConversationInfo


class TestMessageProcessor:
    @pytest.fixture
    def processor(self):
        return MessageProcessor()

    def test_validate_valid_message(self, processor):
        message = {
            "content": "Hello, world!",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "timestamp": datetime.now(timezone.utc),
        }
        assert processor.validate(message) is True

    def test_validate_missing_content(self, processor):
        message = {
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
        }
        with pytest.raises(ValidationError, match="Missing required field: content"):
            processor.validate(message)

    def test_validate_empty_content(self, processor):
        message = {
            "content": "",
            "sender_id": "user_001",
            "sender_name": "Test User",
        }
        with pytest.raises(ValidationError, match="Content must be a non-empty string"):
            processor.validate(message)

    def test_normalize_message(self, processor):
        raw_message = {
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "R:group_001",
            "conversation_type": "group",
            "timestamp": datetime.now(timezone.utc),
            "msg_type": "text",
        }

        standard_message = processor.normalize(raw_message, platform="wework", listener_type="uiautomation")
        assert isinstance(standard_message, StandardMessage)
        assert standard_message.content == "Test message"
        assert standard_message.sender.id == "user_001"
        assert standard_message.conversation.type == "group"

    def test_normalize_message_without_msg_id(self, processor):
        raw_message = {
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
        }

        standard_message = processor.normalize(raw_message)
        assert isinstance(standard_message, StandardMessage)
        assert standard_message.msg_id is not None

    def test_process_message(self, processor):
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "timestamp": datetime.now(timezone.utc),
        }

        result = processor.process(raw_message)
        assert isinstance(result, StandardMessage)
        assert result.msg_id == "test_001"

    def test_process_duplicate_message(self, processor):
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "timestamp": datetime.now(timezone.utc),
        }

        first_result = processor.process(raw_message)
        assert first_result is not None

        second_result = processor.process(raw_message)
        assert second_result is None

    def test_get_stats(self, processor):
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
        }

        processor.process(raw_message)
        stats = processor.stats

        assert isinstance(stats, dict)
        assert stats["total_messages"] == 1
        assert stats["processed"] == 1
        assert stats["duplicates"] == 0
