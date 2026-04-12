from __future__ import annotations

from typing import Any, Dict, Optional

from ..models.tasks import TaskState, TaskStatus, AnalysisResult, ExecutionResultData, RecordingResultData
from ..core.task_manager import TaskManager
from ..core.queue_manager import QueueManager
from ..dispatcher import Dispatcher, HttpDispatcher, InProcessDispatcher
from ...utils import get_logger
from ...exceptions import WeChatAutomationError

logger = get_logger("gateway.router")


class RouterError(WeChatAutomationError):
    pass


class MessageRouter:
    def __init__(
        self,
        task_manager: TaskManager,
        queue_manager: QueueManager,
        dispatcher: Dispatcher,
    ):
        self.task_manager = task_manager
        self.queue_manager = queue_manager
        self.dispatcher = dispatcher

    async def route_new_message(self, task_id: str) -> None:
        task = self.task_manager.get_task(task_id)
        if not task:
            raise RouterError(f"Task not found: {task_id}")

        self.task_manager.update_status(task_id, TaskStatus.FILTERING)

        await self.dispatcher.dispatch_to_analysis(
            task_id=task_id,
            content=task.raw_message,
            msg_id=task.standard_message.get("msg_id", "") if task.standard_message else "",
        )

        logger.info(f"Task {task_id} dispatched to analysis worker")

    async def route_analysis_done(self, task_id: str, analysis_data: Dict[str, Any]) -> None:
        task = self.task_manager.get_task(task_id)
        if not task:
            raise RouterError(f"Task not found: {task_id}")

        is_task = analysis_data.get("is_task", False)

        if not is_task:
            reason = analysis_data.get("reason", "not_task")
            self.task_manager.update_status(task_id, TaskStatus.CANCELLED, error=reason)
            logger.info(f"Task {task_id} cancelled: {reason}")
            return

        analysis = AnalysisResult(
            is_task=True,
            summary=analysis_data.get("summary", ""),
            tech_stack=analysis_data.get("tech_stack", []),
            core_features=analysis_data.get("core_features", []),
            complexity=analysis_data.get("complexity", "simple"),
            category=analysis_data.get("category"),
            reason=analysis_data.get("reason"),
        )
        self.task_manager.set_analysis_result(task_id, analysis)

        self.queue_manager.enqueue(task_id)
        self.task_manager.update_status(task_id, TaskStatus.AWAITING_CONFIRMATION)

        await self.dispatcher.dispatch_to_decision(
            task_id=task_id,
            task_record=task.to_dict(),
            analysis=analysis_data,
        )

        logger.info(f"Task {task_id} dispatched to decision worker")

    async def route_decision(self, task_id: str, action: str) -> None:
        task = self.task_manager.get_task(task_id)
        if not task:
            raise RouterError(f"Task not found: {task_id}")

        self.task_manager.set_decision(task_id, action)

        if action == "approve":
            self.queue_manager.dequeue()
            self.task_manager.update_status(task_id, TaskStatus.APPROVED)
            self.task_manager.update_status(task_id, TaskStatus.EXECUTING)

            summary = ""
            if task.analysis_result:
                summary = task.analysis_result.summary

            await self.dispatcher.dispatch_to_execution(
                task_id=task_id,
                summary=summary,
                raw_message=task.raw_message,
            )
            logger.info(f"Task {task_id} dispatched to execution worker")

        elif action == "reject":
            self.queue_manager.complete_current(success=False)
            self.task_manager.update_status(task_id, TaskStatus.REJECTED)

            await self.dispatcher.dispatch_to_recording(
                task_id=task_id,
                task_record=task.to_dict(),
                success=False,
                message="任务被用户取消",
            )
            logger.info(f"Task {task_id} rejected, dispatched to recording worker")

        elif action == "later":
            self.queue_manager.requeue_task(task_id)
            self.task_manager.update_status(task_id, TaskStatus.LATER)
            logger.info(f"Task {task_id} deferred, requeued")

        elif action == "timeout":
            self.queue_manager.timeout_task(task_id)
            self.task_manager.update_status(task_id, TaskStatus.TIMEOUT)

            await self.dispatcher.dispatch_to_recording(
                task_id=task_id,
                task_record=task.to_dict(),
                success=False,
                message="任务确认超时",
            )
            logger.info(f"Task {task_id} timed out, dispatched to recording worker")

    async def route_execution_done(self, task_id: str, execution_data: Dict[str, Any]) -> None:
        task = self.task_manager.get_task(task_id)
        if not task:
            raise RouterError(f"Task not found: {task_id}")

        result = ExecutionResultData(
            success=execution_data.get("success", False),
            stdout=execution_data.get("stdout", ""),
            stderr=execution_data.get("stderr", ""),
            repo_url=execution_data.get("repo_url"),
            files_created=execution_data.get("files_created", []),
            files_modified=execution_data.get("files_modified", []),
            duration=execution_data.get("duration", 0.0),
            error_message=execution_data.get("error_message"),
        )
        self.task_manager.set_execution_result(task_id, result)

        self.queue_manager.complete_current(success=result.success)
        self.task_manager.update_status(task_id, TaskStatus.RECORDING)

        await self.dispatcher.dispatch_to_recording(
            task_id=task_id,
            task_record=task.to_dict(),
            success=result.success,
            message=f"任务执行{'成功' if result.success else '失败'}",
        )
        logger.info(f"Task {task_id} dispatched to recording worker")

    async def route_recording_done(self, task_id: str, recording_data: Dict[str, Any]) -> None:
        task = self.task_manager.get_task(task_id)
        if not task:
            raise RouterError(f"Task not found: {task_id}")

        result = RecordingResultData(
            success=recording_data.get("success", True),
            record_id=recording_data.get("record_id"),
        )
        self.task_manager.set_recording_result(task_id, result)

        if result.success:
            self.task_manager.update_status(task_id, TaskStatus.COMPLETED)
        else:
            self.task_manager.update_status(task_id, TaskStatus.FAILED, error="Recording failed")

        logger.info(f"Task {task_id} completed")

    async def route_feishu_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        event = callback_data.get("event", {})
        event_type = event.get("type", "")

        if event_type == "card.action.trigger":
            action = event.get("action", {})
            value = action.get("value", {})
            task_id = value.get("task_id")
            action_type = value.get("action")

            if task_id and action_type:
                logger.info(f"Feishu callback: task={task_id}, action={action_type}")
                await self.dispatcher.dispatch_to_decision_callback(
                    task_id=task_id,
                    action=action_type,
                )
                return {"code": 0, "data": {"task_id": task_id, "action": action_type}}

        return {"code": 0}

    async def try_dequeue_next(self) -> Optional[str]:
        task_id = self.queue_manager.dequeue()
        if task_id:
            task = self.task_manager.get_task(task_id)
            if task and task.analysis_result:
                self.task_manager.update_status(task_id, TaskStatus.AWAITING_CONFIRMATION)
                await self.dispatcher.dispatch_to_decision(
                    task_id=task_id,
                    task_record=task.to_dict(),
                    analysis={
                        "summary": task.analysis_result.summary,
                        "tech_stack": task.analysis_result.tech_stack,
                        "core_features": task.analysis_result.core_features,
                        "complexity": task.analysis_result.complexity,
                    },
                )
        return task_id
