"""Unit tests for MessageGateway."""

import pytest
from datetime import datetime, timezone

from src.gateway import MessageGateway, StandardMessage, SenderInfo, ConversationInfo, ValidationError, DuplicateMessageError


class TestMessageGateway:
    """Test cases for MessageGateway."""
    
    @pytest.fixture
    def gateway(self):
        """Create a MessageGateway instance."""
        return MessageGateway()
    
    def test_validate_valid_message(self, gateway):
        """Test validating a valid message."""
        message = {
            "content": "Hello, world!",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "timestamp": datetime.now(timezone.utc)
        }
        assert gateway.validate(message) is True
    
    def test_validate_missing_content(self, gateway):
        """Test validating a message with missing content."""
        message = {
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001"
        }
        with pytest.raises(ValidationError, match="Missing required field: content"):
            gateway.validate(message)
    
    def test_validate_empty_content(self, gateway):
        """Test validating a message with empty content."""
        message = {
            "content": "",
            "sender_id": "user_001",
            "sender_name": "Test User"
        }
        with pytest.raises(ValidationError, match="Content must be a non-empty string"):
            gateway.validate(message)
    
    def test_normalize_message(self, gateway):
        """Test normalizing a message."""
        raw_message = {
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "R:group_001",
            "conversation_type": "group",
            "timestamp": datetime.now(timezone.utc),
            "msg_type": "text"
        }
        
        standard_message = gateway.normalize(raw_message, platform="wework", listener_type="uiautomation")
        assert isinstance(standard_message, StandardMessage)
        assert standard_message.content == "Test message"
        assert standard_message.sender.id == "user_001"
        assert standard_message.conversation.type == "group"
    
    def test_normalize_message_without_msg_id(self, gateway):
        """Test normalizing a message without msg_id."""
        raw_message = {
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User"
        }
        
        standard_message = gateway.normalize(raw_message)
        assert isinstance(standard_message, StandardMessage)
        assert standard_message.msg_id is not None
    
    def test_process_message(self, gateway):
        """Test processing a message."""
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "timestamp": datetime.now(timezone.utc)
        }
        
        result = gateway.process(raw_message)
        assert isinstance(result, StandardMessage)
        assert result.msg_id == "test_001"
    
    def test_process_duplicate_message(self, gateway):
        """Test processing a duplicate message."""
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "timestamp": datetime.now(timezone.utc)
        }
        
        # First process should succeed
        first_result = gateway.process(raw_message)
        assert first_result is not None
        
        # Second process should return None (duplicate)
        second_result = gateway.process(raw_message)
        assert second_result is None
    
    def test_register_handler(self, gateway):
        """Test registering a message handler."""
        handler_called = False
        
        def test_handler(message):
            nonlocal handler_called
            handler_called = True
        
        gateway.register_handler(test_handler)
        
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User"
        }
        
        gateway.process(raw_message)
        assert handler_called
    
    def test_get_stats(self, gateway):
        """Test getting gateway statistics."""
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User"
        }
        
        gateway.process(raw_message)
        stats = gateway.stats
        
        assert isinstance(stats, dict)
        assert stats["total_messages"] == 1
        assert stats["processed"] == 1
        assert stats["duplicates"] == 0
    
    def test_reset_stats(self, gateway):
        """Test resetting gateway statistics."""
        raw_message = {
            "msg_id": "test_001",
            "content": "Test message",
            "sender_id": "user_001",
            "sender_name": "Test User"
        }
        
        gateway.process(raw_message)
        assert gateway.stats["total_messages"] == 1
        
        gateway.reset_stats()
        assert gateway.stats["total_messages"] == 0