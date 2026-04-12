from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gateway.core.router import MessageRouter
from src.gateway.core.task_manager import TaskManager
from src.gateway.core.queue_manager import QueueManager
from src.gateway.models.tasks import TaskStatus


class TestMessageRouter:
    def setup_method(self):
        self.task_manager = TaskManager()
        self.queue_manager = QueueManager()
        self.dispatcher = AsyncMock()
        self.router = MessageRouter(
            task_manager=self.task_manager,
            queue_manager=self.queue_manager,
            dispatcher=self.dispatcher,
        )

    @pytest.mark.asyncio
    async def test_route_new_message(self):
        task = self.task_manager.create_task("develop a login feature")
        await self.router.route_new_message(task.task_id)
        assert self.task_manager.get_task(task.task_id).status == TaskStatus.FILTERING
        self.dispatcher.dispatch_to_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_new_message_not_found(self):
        from src.gateway.core.router import RouterError
        with pytest.raises(RouterError):
            await self.router.route_new_message("nonexistent")

    @pytest.mark.asyncio
    async def test_route_analysis_done_is_task(self):
        task = self.task_manager.create_task("develop login")
        self.task_manager.update_status(task.task_id, TaskStatus.FILTERING)
        analysis_data = {
            "is_task": True,
            "summary": "login feature",
            "tech_stack": ["Python"],
            "core_features": ["auth"],
            "complexity": "simple",
        }
        await self.router.route_analysis_done(task.task_id, analysis_data)
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.AWAITING_CONFIRMATION
        assert found.analysis_result.summary == "login feature"
        self.dispatcher.dispatch_to_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_analysis_done_not_task(self):
        task = self.task_manager.create_task("casual chat")
        self.task_manager.update_status(task.task_id, TaskStatus.FILTERING)
        analysis_data = {"is_task": False, "reason": "not_task"}
        await self.router.route_analysis_done(task.task_id, analysis_data)
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_route_analysis_done_not_found(self):
        from src.gateway.core.router import RouterError
        with pytest.raises(RouterError):
            await self.router.route_analysis_done("nonexistent", {"is_task": True})

    @pytest.mark.asyncio
    async def test_route_decision_approve(self):
        task = self.task_manager.create_task("develop login")
        self.task_manager.update_status(task.task_id, TaskStatus.FILTERING)
        from src.gateway.models.tasks import AnalysisResult
        self.task_manager.set_analysis_result(task.task_id, AnalysisResult(summary="login"))
        self.task_manager.update_status(task.task_id, TaskStatus.AWAITING_CONFIRMATION)
        self.queue_manager.enqueue(task.task_id)
        self.queue_manager.dequeue()

        await self.router.route_decision(task.task_id, "approve")
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.EXECUTING
        self.dispatcher.dispatch_to_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_decision_reject(self):
        task = self.task_manager.create_task("bad task")
        self.task_manager.update_status(task.task_id, TaskStatus.AWAITING_CONFIRMATION)
        self.queue_manager.enqueue(task.task_id)
        self.queue_manager.dequeue()

        await self.router.route_decision(task.task_id, "reject")
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.REJECTED
        self.dispatcher.dispatch_to_recording.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_decision_later(self):
        task = self.task_manager.create_task("deferred task")
        self.task_manager.update_status(task.task_id, TaskStatus.AWAITING_CONFIRMATION)
        self.queue_manager.enqueue(task.task_id)
        self.queue_manager.dequeue()

        await self.router.route_decision(task.task_id, "later")
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.LATER

    @pytest.mark.asyncio
    async def test_route_decision_timeout(self):
        task = self.task_manager.create_task("timeout task")
        self.task_manager.update_status(task.task_id, TaskStatus.AWAITING_CONFIRMATION)
        self.queue_manager.enqueue(task.task_id)
        self.queue_manager.dequeue()

        await self.router.route_decision(task.task_id, "timeout")
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.TIMEOUT
        self.dispatcher.dispatch_to_recording.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_decision_not_found(self):
        from src.gateway.core.router import RouterError
        with pytest.raises(RouterError):
            await self.router.route_decision("nonexistent", "approve")

    @pytest.mark.asyncio
    async def test_route_execution_done_success(self):
        task = self.task_manager.create_task("exec task")
        self.task_manager.update_status(task.task_id, TaskStatus.EXECUTING)
        self.queue_manager.enqueue(task.task_id)
        self.queue_manager.dequeue()
        self.queue_manager._current_task_id = task.task_id

        execution_data = {
            "success": True,
            "stdout": "done",
            "stderr": "",
            "repo_url": "https://github.com/test/repo",
            "duration": 10.5,
        }
        await self.router.route_execution_done(task.task_id, execution_data)
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.RECORDING
        assert found.execution_result.repo_url == "https://github.com/test/repo"
        self.dispatcher.dispatch_to_recording.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_execution_done_failure(self):
        task = self.task_manager.create_task("fail task")
        self.task_manager.update_status(task.task_id, TaskStatus.EXECUTING)
        self.queue_manager.enqueue(task.task_id)
        self.queue_manager.dequeue()
        self.queue_manager._current_task_id = task.task_id

        execution_data = {
            "success": False,
            "stderr": "error occurred",
            "error_message": "error occurred",
        }
        await self.router.route_execution_done(task.task_id, execution_data)
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.RECORDING

    @pytest.mark.asyncio
    async def test_route_recording_done_success(self):
        task = self.task_manager.create_task("rec task")
        self.task_manager.update_status(task.task_id, TaskStatus.RECORDING)
        recording_data = {"success": True, "record_id": "rec_001"}
        await self.router.route_recording_done(task.task_id, recording_data)
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_route_recording_done_failure(self):
        task = self.task_manager.create_task("rec fail")
        self.task_manager.update_status(task.task_id, TaskStatus.RECORDING)
        recording_data = {"success": False}
        await self.router.route_recording_done(task.task_id, recording_data)
        found = self.task_manager.get_task(task.task_id)
        assert found.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_route_feishu_callback_card_action(self):
        callback_data = {
            "event": {
                "type": "card.action.trigger",
                "action": {
                    "value": {"task_id": "task_123", "action": "approve"},
                },
            }
        }
        result = await self.router.route_feishu_callback(callback_data)
        assert result["code"] == 0
        assert result["data"]["task_id"] == "task_123"
        self.dispatcher.dispatch_to_decision_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_feishu_callback_unknown_event(self):
        callback_data = {"event": {"type": "unknown"}}
        result = await self.router.route_feishu_callback(callback_data)
        assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_try_dequeue_next(self):
        task = self.task_manager.create_task("next task")
        from src.gateway.models.tasks import AnalysisResult
        self.task_manager.set_analysis_result(task.task_id, AnalysisResult(summary="next"))
        self.task_manager.update_status(task.task_id, TaskStatus.AWAITING_CONFIRMATION)
        self.queue_manager.enqueue(task.task_id)

        result = await self.router.try_dequeue_next()
        assert result == task.task_id
        self.dispatcher.dispatch_to_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_dequeue_next_empty(self):
        result = await self.router.try_dequeue_next()
        assert result is None
