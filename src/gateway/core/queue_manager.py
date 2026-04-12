from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ...utils import get_logger
from ...exceptions import WeChatAutomationError

logger = get_logger("gateway.queue_manager")


class QueueFullError(WeChatAutomationError):
    pass


@dataclass
class QueueConfig:
    max_size: int = 20
    confirmation_timeout: int = 10800
    processing_timeout: int = 3600
    retry_delay: int = 60
    cleanup_interval: int = 300
    enable_priority: bool = False


@dataclass
class QueuedItem:
    task_id: str
    priority: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueueManager:
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or QueueConfig()
        self._queue: deque = deque()
        self._current_task_id: Optional[str] = None
        self._task_index: Dict[str, QueuedItem] = {}
        self._lock = threading.Lock()
        self._stats = {
            "total_enqueued": 0,
            "total_dequeued": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_timeout": 0,
        }

    def enqueue(self, task_id: str, priority: int = 1, metadata: Optional[Dict[str, Any]] = None) -> QueuedItem:
        with self._lock:
            if len(self._queue) >= self.config.max_size:
                raise QueueFullError(f"Queue is full (max: {self.config.max_size})")

            item = QueuedItem(
                task_id=task_id,
                priority=priority,
                metadata=metadata or {},
            )

            self._queue.append(item)
            self._task_index[task_id] = item
            self._stats["total_enqueued"] += 1

        logger.info(f"Task {task_id} enqueued (position: {len(self._queue)})")
        return item

    def dequeue(self) -> Optional[str]:
        with self._lock:
            if not self._queue:
                return None

            if self._current_task_id is not None:
                return None

            item = self._queue.popleft()
            self._current_task_id = item.task_id
            self._stats["total_dequeued"] += 1

        logger.info(f"Task {item.task_id} dequeued for processing")
        return item.task_id

    def complete_current(self, success: bool = True) -> Optional[str]:
        with self._lock:
            if not self._current_task_id:
                return None

            task_id = self._current_task_id
            self._current_task_id = None

            if success:
                self._stats["total_completed"] += 1
            else:
                self._stats["total_failed"] += 1

            self._task_index.pop(task_id, None)

        logger.info(f"Task {task_id} completed (success={success})")
        return task_id

    def cancel_task(self, task_id: str, reason: Optional[str] = None) -> bool:
        with self._lock:
            if task_id not in self._task_index:
                return False

            item = self._task_index.pop(task_id)

            if self._current_task_id == task_id:
                self._current_task_id = None

            try:
                self._queue.remove(item)
            except ValueError:
                pass

            self._stats["total_cancelled"] += 1

        logger.info(f"Task {task_id} cancelled: {reason}")
        return True

    def requeue_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id not in self._task_index:
                return False

            if len(self._queue) >= self.config.max_size:
                return False

            item = self._task_index[task_id]
            item.metadata["requeue_count"] = item.metadata.get("requeue_count", 0) + 1

            if self._current_task_id == task_id:
                self._current_task_id = None

            self._queue.append(item)

        logger.info(f"Task {task_id} requeued")
        return True

    def timeout_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id not in self._task_index:
                return False

            if self._current_task_id == task_id:
                self._current_task_id = None

            self._task_index.pop(task_id, None)
            self._stats["total_timeout"] += 1

        logger.warning(f"Task {task_id} timed out")
        return True

    def get_pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def current_task(self) -> Optional[str]:
        with self._lock:
            return self._current_task_id

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                **self._stats,
                "queue_size": len(self._queue),
                "max_size": self.config.max_size,
                "current_task": self._current_task_id,
            }
