"""Unit tests for TaskFilter."""

import pytest
from unittest.mock import Mock, patch

from src.filter import TaskFilter, FilterResult, DeduplicationResult


class TestTaskFilter:
    """Test cases for TaskFilter."""
    
    @pytest.fixture
    def filter(self):
        """Create a TaskFilter instance."""
        return TaskFilter()
    
    def test_classify_task_message(self, filter):
        """Test classifying a task message."""
        message = "开发一个用户登录功能，使用 Python Flask 框架"
        result = filter.classify(message)
        assert isinstance(result, FilterResult)
        assert result.is_task is True
        assert result.confidence >= 0.5
    
    def test_classify_non_task_message(self, filter):
        """Test classifying a non-task message."""
        message = "今天天气真好，适合出去游玩"
        result = filter.classify(message)
        assert isinstance(result, FilterResult)
        assert result.is_task is False
        assert result.confidence < 0.5
    
    def test_check_duplicate(self, filter):
        """Test checking for duplicate messages."""
        message1 = "开发一个用户登录功能"
        message2 = "开发一个用户登录功能"
        
        # First message should not be duplicate
        result1 = filter.check_duplicate(message1, "msg_001")
        assert isinstance(result1, DeduplicationResult)
        assert result1.is_duplicate is False
        
        # Second message should be duplicate
        result2 = filter.check_duplicate(message2, "msg_002")
        assert isinstance(result2, DeduplicationResult)
        assert result2.is_duplicate is True
    
    def test_check_non_duplicate(self, filter):
        """Test checking for non-duplicate messages."""
        message1 = "开发一个用户登录功能"
        message2 = "开发一个用户注册功能"
        
        result1 = filter.check_duplicate(message1, "msg_001")
        result2 = filter.check_duplicate(message2, "msg_002")
        
        assert result1.is_duplicate is False
        assert result2.is_duplicate is False
    
    def test_filter_task_message(self, filter):
        """Test filtering a task message."""
        message = "开发一个用户登录功能"
        filter_result, dedup_result = filter.filter(message, "msg_001")
        
        assert isinstance(filter_result, FilterResult)
        assert isinstance(dedup_result, DeduplicationResult)
        assert filter_result.is_task is True
        assert dedup_result.is_duplicate is False
    
    def test_filter_duplicate_message(self, filter):
        """Test filtering a duplicate message."""
        message = "开发一个用户登录功能"
        
        # First filter should pass
        filter_result1, dedup_result1 = filter.filter(message, "msg_001")
        assert filter_result1.is_task is True
        assert dedup_result1.is_duplicate is False
        
        # Second filter should detect duplicate
        filter_result2, dedup_result2 = filter.filter(message, "msg_002")
        assert filter_result2.is_task is False  # Should be false due to duplication
        assert dedup_result2.is_duplicate is True
    
    def test_filter_non_task_message(self, filter):
        """Test filtering a non-task message."""
        message = "今天天气真好"
        filter_result, dedup_result = filter.filter(message, "msg_001")
        
        assert filter_result.is_task is False
        assert dedup_result.is_duplicate is False
    
    def test_get_embedding(self, filter):
        """Test getting embedding for text."""
        text = "Test message"
        embedding = filter.get_embedding(text)
        # Should return None if embedding model is not available
        assert embedding is None
    
    def test_cosine_similarity(self, filter):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 0.0]
        vec3 = [0.0, 1.0]
        
        similarity1 = filter.cosine_similarity(vec1, vec2)
        similarity2 = filter.cosine_similarity(vec1, vec3)
        
        assert similarity1 == 1.0
        assert similarity2 == 0.0
    
    def test_get_stats(self, filter):
        """Test getting filter statistics."""
        message = "开发一个用户登录功能"
        filter.filter(message, "msg_001")
        
        stats = filter.stats
        assert isinstance(stats, dict)
        assert stats["total_messages"] == 1
        assert stats["tasks_detected"] >= 0
        assert stats["duplicates_found"] >= 0
    
    def test_clear_history(self, filter):
        """Test clearing filter history."""
        message = "开发一个用户登录功能"
        filter.filter(message, "msg_001")
        
        assert len(filter._message_history) > 0
        filter.clear_history()
        assert len(filter._message_history) == 0