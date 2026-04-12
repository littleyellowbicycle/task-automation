"""Unit tests for WorkflowOrchestrator."""

import asyncio
import pytest
from unittest.mock import Mock, patch

from src.workflow_orchestrator import WorkflowOrchestrator, WorkflowState
from src.gateway.models.messages import StandardMessage, SenderInfo, ConversationInfo
from src.gateway.core.message_processor import MessageProcessor
from src.filter import TaskFilter, FilterResult, DeduplicationResult
from src.queue import TaskQueue, TaskStatus
from src.feishu_recorder.models import TaskRecord
from src.wechat_listener.models import TaskMessage, WeChatMessage, MessageType, ConversationType


class TestWorkflowOrchestrator:
    """Test cases for WorkflowOrchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create a WorkflowOrchestrator instance."""
        return WorkflowOrchestrator(dry_run=True)
    
    @pytest.fixture
    def mock_message(self):
        """Create a mock StandardMessage."""
        sender = SenderInfo(id="user_001", name="Test User")
        conversation = ConversationInfo(id="group_001", type="group", name="Test Group")
        return StandardMessage(
            msg_id="msg_001",
            platform="wework",
            listener_type="uiautomation",
            content="开发一个用户登录功能，使用 Python Flask 框架",
            sender=sender,
            conversation=conversation,
            timestamp=Mock()
        )
    
    @pytest.fixture
    def mock_task_message(self):
        """Create a mock TaskMessage."""
        original_message = WeChatMessage(
            msg_id="msg_001",
            msg_type=MessageType.TEXT,
            content="开发一个用户登录功能，使用 Python Flask 框架",
            conversation_id="R:group_001",
            conversation_type=ConversationType.GROUP,
            sender_id="user_001",
            sender_name="Test User",
            timestamp=Mock()
        )
        return TaskMessage(
            original_message=original_message,
            is_project_task=True,
            keywords_matched=["开发"],
            confidence_score=0.8
        )
    
    @pytest.mark.asyncio
    async def test_process_raw_message(self, orchestrator):
        """Test processing a raw message."""
        raw_message = {
            "msg_id": "test_001",
            "content": "开发一个用户登录功能",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "conversation_type": "group",
            "timestamp": Mock(),
            "msg_type": "text"
        }
        
        # Mock the filter to return a task
        with patch.object(orchestrator.task_filter, 'filter') as mock_filter:
            mock_filter.return_value = (
                FilterResult(is_task=True, confidence=0.9),
                DeduplicationResult(is_duplicate=False)
            )
            
            result = await orchestrator.process_raw_message(raw_message)
            assert result is not None
            assert result.msg_id == "test_001"
    
    @pytest.mark.asyncio
    async def test_process_duplicate_message(self, orchestrator):
        """Test processing a duplicate message."""
        raw_message = {
            "msg_id": "test_001",
            "content": "开发一个用户登录功能",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "conversation_type": "group",
            "timestamp": Mock(),
            "msg_type": "text"
        }
        
        # Mock the gateway to return None for duplicate
        with patch.object(orchestrator.message_gateway, 'process') as mock_process:
            mock_process.return_value = None
            
            result = await orchestrator.process_raw_message(raw_message)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_process_non_task_message(self, orchestrator):
        """Test processing a non-task message."""
        raw_message = {
            "msg_id": "test_001",
            "content": "今天天气真好",
            "sender_id": "user_001",
            "sender_name": "Test User",
            "conversation_id": "group_001",
            "conversation_type": "group",
            "timestamp": Mock(),
            "msg_type": "text"
        }
        
        # Mock the filter to return non-task
        with patch.object(orchestrator.task_filter, 'filter') as mock_filter:
            mock_filter.return_value = (
                FilterResult(is_task=False, confidence=0.1),
                DeduplicationResult(is_duplicate=False)
            )
            
            result = await orchestrator.process_raw_message(raw_message)
            assert result is not None  # Gateway returns message, but filter rejects it
    
    @pytest.mark.asyncio
    async def test_run_backward_compatibility(self, orchestrator, mock_task_message):
        """Test backward compatibility of run method."""
        result = await orchestrator.run(mock_task_message)
        assert isinstance(result, TaskRecord)
        assert result.task_id.startswith("task_")
        assert result.raw_message == mock_task_message.original_message.content
    
    def test_get_state(self, orchestrator):
        """Test get_state method."""
        assert orchestrator.get_state() == WorkflowState.IDLE
    
    def test_get_current_task(self, orchestrator):
        """Test get_current_task method."""
        assert orchestrator.get_current_task() is None
    
    def test_get_queue_stats(self, orchestrator):
        """Test get_queue_stats method."""
        stats = orchestrator.get_queue_stats()
        assert isinstance(stats, dict)
        assert "queue_size" in stats
    
    def test_get_filter_stats(self, orchestrator):
        """Test get_filter_stats method."""
        stats = orchestrator.get_filter_stats()
        assert isinstance(stats, dict)
        assert "total_messages" in stats
    
    def test_get_gateway_stats(self, orchestrator):
        """Test get_gateway_stats method."""
        stats = orchestrator.get_gateway_stats()
        assert isinstance(stats, dict)
        assert "total_messages" in stats