from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.tasks import TaskState, TaskStatus, AnalysisResult, ExecutionResultData, RecordingResultData
from ...utils import get_logger
from ...exceptions import WeChatAutomationError

logger = get_logger("gateway.task_manager")


class TaskManagerError(WeChatAutomationError):
    pass


class TaskManager:
    def __init__(self, max_tasks: int = 1000):
        self._tasks: Dict[str, TaskState] = {}
        self._lock = threading.Lock()
        self._max_tasks = max_tasks
        self._stats = {
            "total_created": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
        }

    def create_task(self, raw_message: str, standard_message: Optional[Dict[str, Any]] = None) -> TaskState:
        task_id = self._generate_task_id(raw_message)
        with self._lock:
            if task_id in self._tasks:
                logger.warning(f"Task already exists: {task_id}")
                return self._tasks[task_id]

            task = TaskState(
                task_id=task_id,
                status=TaskStatus.RECEIVED,
                raw_message=raw_message,
                standard_message=standard_message,
            )
            self._tasks[task_id] = task
            self._stats["total_created"] += 1

            if len(self._tasks) > self._max_tasks:
                self._cleanup_old_tasks()

        logger.info(f"Task created: {task_id}")
        return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            return self._tasks.get(task_id)

    def update_status(self, task_id: str, status: TaskStatus, error: Optional[str] = None) -> Optional[TaskState]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.warning(f"Task not found: {task_id}")
                return None

            old_status = task.status
            task.update_status(status, error)

            if status == TaskStatus.COMPLETED:
                self._stats["total_completed"] += 1
            elif status == TaskStatus.FAILED:
                self._stats["total_failed"] += 1
            elif status in (TaskStatus.CANCELLED, TaskStatus.REJECTED):
                self._stats["total_cancelled"] += 1

        logger.info(f"Task {task_id}: {old_status.value} → {status.value}")
        return task

    def set_analysis_result(self, task_id: str, analysis: AnalysisResult) -> Optional[TaskState]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.analysis_result = analysis
            task.updated_at = datetime.now(timezone.utc)
        return task

    def set_decision(self, task_id: str, decision: str) -> Optional[TaskState]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.decision = decision
            task.updated_at = datetime.now(timezone.utc)
        return task

    def set_execution_result(self, task_id: str, result: ExecutionResultData) -> Optional[TaskState]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.execution_result = result
            task.updated_at = datetime.now(timezone.utc)
        return task

    def set_recording_result(self, task_id: str, result: RecordingResultData) -> Optional[TaskState]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.recording_result = result
            task.updated_at = datetime.now(timezone.utc)
        return task

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        with self._lock:
            tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        tasks.sort(key=lambda t: t.created_at, reverse=True)

        total = len(tasks)
        start = (page - 1) * page_size
        end = start + page_size
        items = tasks[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [t.to_dict() for t in items],
        }

    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskState]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status == status]

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            status_counts = {}
            for task in self._tasks.values():
                s = task.status.value
                status_counts[s] = status_counts.get(s, 0) + 1

            return {
                **self._stats,
                "active_tasks": len(self._tasks),
                "status_counts": status_counts,
            }

    def _generate_task_id(self, message: str) -> str:
        unique_str = f"{message}_{datetime.now(timezone.utc).isoformat()}"
        hash_part = hashlib.md5(unique_str.encode()).hexdigest()[:8]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"task_{ts}_{hash_part}"

    def _cleanup_old_tasks(self) -> None:
        terminal_statuses = {
            TaskStatus.COMPLETED, TaskStatus.FAILED,
            TaskStatus.CANCELLED, TaskStatus.REJECTED,
            TaskStatus.TIMEOUT,
        }
        to_remove = []
        for task_id, task in self._tasks.items():
            if task.status in terminal_statuses:
                to_remove.append(task_id)

        for task_id in to_remove[:len(to_remove) // 2]:
            self._tasks.pop(task_id, None)

        logger.info(f"Cleaned up {min(len(to_remove), len(to_remove) // 2)} old tasks")
