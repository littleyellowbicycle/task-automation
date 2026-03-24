"""Decision manager for user confirmation workflow."""

import asyncio
from datetime import datetime
from typing import Optional, Callable
from enum import Enum

from ..wechat_listener.models import TaskMessage
from ..feishu_recorder.models import TaskRecord, TaskStatus
from ..utils import get_logger
from ..exceptions import ConfirmationTimeoutError

logger = get_logger("decision_manager")


class ConfirmationResult(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class DecisionManager:
    """
    Manages user confirmation for task execution.
    """
    
    def __init__(self, confirm_timeout: int = 300, on_confirm: Optional[Callable] = None, on_cancel: Optional[Callable] = None):
        self.confirm_timeout = confirm_timeout
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._pending_confirmations: dict = {}
    
    def format_confirmation_message(self, task_record: TaskRecord) -> str:
        """Format a confirmation message for user."""
        tech_stack = ", ".join(task_record.tech_stack) if task_record.tech_stack else "未指定"
        features = "\n".join(f"- {f}" for f in task_record.core_features) if task_record.core_features else "- 未指定"
        
        return f"""📋 **任务确认**

**摘要**: {task_record.summary}
**技术栈**: {tech_stack}
**核心功能**:
{features}
**预估复杂度**: {task_record.estimated_complexity}

⏱️ 超时时间: {self.confirm_timeout // 60}分钟

回复 "确认" 执行 / "取消" 终止"""
    
    async def request_confirmation(self, task_record: TaskRecord) -> ConfirmationResult:
        """
        Request user confirmation for a task.
        
        Args:
            task_record: Task to confirm
            
        Returns:
            ConfirmationResult
        """
        task_id = task_record.task_id
        logger.info(f"Requesting confirmation for task: {task_id}")
        
        # Format and send confirmation message (via WeChat)
        message = self.format_confirmation_message(task_record)
        logger.info(f"Confirmation message:\n{message}")
        
        # Store pending confirmation
        self._pending_confirmations[task_id] = {
            "task_record": task_record,
            "requested_at": datetime.now(),
            "result": None,
        }
        
        try:
            # Wait for confirmation with timeout
            result = await self._wait_for_response(task_id)
            
            if result == ConfirmationResult.CONFIRMED and self.on_confirm:
                await self.on_confirm(task_record)
            elif result == ConfirmationResult.CANCELLED and self.on_cancel:
                await self.on_cancel(task_record)
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Confirmation timeout for task: {task_id}")
            return ConfirmationResult.TIMEOUT
        finally:
            self._pending_confirmations.pop(task_id, None)
    
    async def _wait_for_response(self, task_id: str) -> ConfirmationResult:
        """Wait for user response (placeholder - integrate with WeChat listener)."""
        # In real implementation, this would wait for WeChat private message response
        try:
            await asyncio.wait_for(asyncio.sleep(1), timeout=self.confirm_timeout)
            return ConfirmationResult.CONFIRMED
        except asyncio.TimeoutError:
            return ConfirmationResult.TIMEOUT
    
    async def confirm(self, task_id: str) -> bool:
        """Mark a task as confirmed by ID."""
        if task_id in self._pending_confirmations:
            self._pending_confirmations[task_id]["result"] = ConfirmationResult.CONFIRMED
            return True
        return False
    
    async def cancel(self, task_id: str) -> bool:
        """Mark a task as cancelled by ID."""
        if task_id in self._pending_confirmations:
            self._pending_confirmations[task_id]["result"] = ConfirmationResult.CANCELLED
            return True
        return False
