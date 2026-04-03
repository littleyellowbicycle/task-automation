"""Task Queue module for managing task execution order."""

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("queue")


class QueueError(WeChatAutomationError):
    """Base exception for queue errors."""
    pass


class QueueFullError(QueueError):
    """Raised when queue is full."""
    pass


class TaskTimeoutError(QueueError):
    """Raised when task times out."""
    pass


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class QueuedTask:
    """A task in the queue."""
    task_id: str
    data: Dict[str, Any]
    status: TaskStatus = TaskStatus.QUEUED
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, status: TaskStatus, error: Optional[str] = None) -> None:
        """Update task status."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        if error:
            self.error_message = error
        if status == TaskStatus.PROCESSING:
            self.started_at = datetime.now(timezone.utc)
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT):
            self.completed_at = datetime.now(timezone.utc)
    
    @property
    def age_seconds(self) -> float:
        """Get task age in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()
    
    @property
    def processing_seconds(self) -> Optional[float]:
        """Get processing time in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()


@dataclass
class QueueConfig:
    """Configuration for task queue."""
    max_size: int = 20
    confirmation_timeout: int = 10800  # 3 hours
    processing_timeout: int = 3600     # 1 hour
    retry_delay: int = 60              # 1 minute
    cleanup_interval: int = 300        # 5 minutes
    enable_priority: bool = False


class TaskQueue:
    """
    Task Queue for managing task execution order.
    
    Features:
    - Serial task processing
    - Configurable queue size
    - Timeout handling
    - Task status tracking
    - Statistics and monitoring
    """
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or QueueConfig()
        self._queue: deque = deque()
        self._current_task: Optional[QueuedTask] = None
        self._completed_tasks: List[QueuedTask] = []
        self._task_index: Dict[str, QueuedTask] = {}
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._running = False
        self._processor: Optional[Callable[[QueuedTask], Any]] = None
        self._on_task_added: Optional[Callable[[QueuedTask], None]] = None
        self._on_task_started: Optional[Callable[[QueuedTask], None]] = None
        self._on_task_completed: Optional[Callable[[QueuedTask], None]] = None
        self._on_task_failed: Optional[Callable[[QueuedTask], None]] = None
        self._stats = {
            "total_added": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_timeout": 0,
        }
    
    def set_processor(self, processor: Callable[[QueuedTask], Any]) -> None:
        """Set the task processor function."""
        self._processor = processor
    
    def on_task_added(self, callback: Callable[[QueuedTask], None]) -> None:
        """Set callback for when a task is added."""
        self._on_task_added = callback
    
    def on_task_started(self, callback: Callable[[QueuedTask], None]) -> None:
        """Set callback for when a task starts processing."""
        self._on_task_started = callback
    
    def on_task_completed(self, callback: Callable[[QueuedTask], None]) -> None:
        """Set callback for when a task completes."""
        self._on_task_completed = callback
    
    def on_task_failed(self, callback: Callable[[QueuedTask], None]) -> None:
        """Set callback for when a task fails."""
        self._on_task_failed = callback
    
    @property
    def size(self) -> int:
        """Get current queue size."""
        with self._lock:
            return len(self._queue)
    
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return len(self._queue) == 0 and self._current_task is None
    
    @property
    def is_full(self) -> bool:
        """Check if queue is full."""
        with self._lock:
            return len(self._queue) >= self.config.max_size
    
    @property
    def current_task(self) -> Optional[QueuedTask]:
        """Get the current task being processed."""
        with self._lock:
            return self._current_task
    
    def enqueue(
        self,
        task_id: str,
        data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> QueuedTask:
        """
        Add a task to the queue.
        
        Args:
            task_id: Unique task identifier
            data: Task data
            priority: Task priority
            metadata: Additional metadata
            
        Returns:
            The queued task
            
        Raises:
            QueueFullError: If queue is full
        """
        with self._lock:
            if len(self._queue) >= self.config.max_size:
                raise QueueFullError(
                    f"Queue is full (max: {self.config.max_size})"
                )
            
            task = QueuedTask(
                task_id=task_id,
                data=data,
                priority=priority,
                metadata=metadata or {},
            )
            
            if self.config.enable_priority:
                inserted = False
                for i, existing in enumerate(self._queue):
                    if task.priority > existing.priority:
                        self._queue.insert(i, task)
                        inserted = True
                        break
                if not inserted:
                    self._queue.append(task)
            else:
                self._queue.append(task)
            
            self._task_index[task_id] = task
            self._stats["total_added"] += 1
            
            logger.info(f"Task {task_id} added to queue (position: {len(self._queue)}, priority: {priority.name})")
            
            self._condition.notify()
        
        if self._on_task_added:
            try:
                self._on_task_added(task)
            except Exception as e:
                logger.error(f"Task added callback failed: {e}")
        
        return task
    
    def dequeue(self, timeout: float = 1.0) -> Optional[QueuedTask]:
        """
        Get the next task from the queue.
        
        Args:
            timeout: Maximum time to wait for a task
            
        Returns:
            The next task, or None if timeout
        """
        with self._condition:
            if not self._queue and self._current_task is None:
                self._condition.wait(timeout)
            
            if not self._queue:
                return None
            
            if self._current_task is not None:
                return None
            
            task = self._queue.popleft()
            task.update_status(TaskStatus.PROCESSING)
            self._current_task = task
            
            logger.info(f"Task {task.task_id} dequeued for processing")
        
        if self._on_task_started:
            try:
                self._on_task_started(task)
            except Exception as e:
                logger.error(f"Task started callback failed: {e}")
        
        return task
    
    def complete_task(self, task_id: str, success: bool = True, error: Optional[str] = None) -> None:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task identifier
            success: Whether the task succeeded
            error: Error message if failed
        """
        with self._lock:
            task = self._task_index.get(task_id)
            if not task:
                logger.warning(f"Task {task_id} not found for completion")
                return
            
            if success:
                task.update_status(TaskStatus.COMPLETED)
                self._stats["total_completed"] += 1
                logger.info(f"Task {task_id} completed successfully")
            else:
                task.update_status(TaskStatus.FAILED, error=error)
                self._stats["total_failed"] += 1
                logger.error(f"Task {task_id} failed: {error}")
            
            self._completed_tasks.append(task)
            if len(self._completed_tasks) > 100:
                self._completed_tasks.pop(0)
            
            if self._current_task and self._current_task.task_id == task_id:
                self._current_task = None
            
            self._condition.notify()
        
        callback = self._on_task_completed if success else self._on_task_failed
        if callback:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Task callback failed: {e}")
    
    def cancel_task(self, task_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task identifier
            reason: Cancellation reason
            
        Returns:
            True if cancelled, False if not found
        """
        with self._lock:
            task = self._task_index.get(task_id)
            if not task:
                return False
            
            if task.status == TaskStatus.PROCESSING:
                logger.warning(f"Cannot cancel task {task_id} that is currently processing")
                return False
            
            if task in self._queue:
                self._queue.remove(task)
            
            task.update_status(TaskStatus.CANCELLED, error=reason)
            self._completed_tasks.append(task)
            self._stats["total_cancelled"] += 1
            
            logger.info(f"Task {task_id} cancelled: {reason}")
            
            return True
    
    def timeout_task(self, task_id: str) -> bool:
        """
        Mark a task as timed out.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if timed out, False if not found
        """
        with self._lock:
            task = self._task_index.get(task_id)
            if not task:
                return False
            
            task.update_status(TaskStatus.TIMEOUT, error="Task timed out")
            
            if self._current_task and self._current_task.task_id == task_id:
                self._current_task = None
            
            self._completed_tasks.append(task)
            self._stats["total_timeout"] += 1
            
            logger.warning(f"Task {task_id} timed out")
            
            self._condition.notify()
        
        if self._on_task_failed:
            try:
                self._on_task_failed(task)
            except Exception as e:
                logger.error(f"Task failed callback failed: {e}")
        
        return True
    
    def get_task(self, task_id: str) -> Optional[QueuedTask]:
        """Get a task by ID."""
        with self._lock:
            return self._task_index.get(task_id)
    
    def get_all_tasks(self) -> List[QueuedTask]:
        """Get all tasks (queued and current)."""
        with self._lock:
            tasks = list(self._queue)
            if self._current_task:
                tasks.insert(0, self._current_task)
            return tasks
    
    def get_pending_count(self) -> int:
        """Get count of pending tasks."""
        with self._lock:
            return len(self._queue)
    
    def clear_completed(self) -> int:
        """Clear completed tasks and return count."""
        with self._lock:
            count = len(self._completed_tasks)
            for task in self._completed_tasks:
                self._task_index.pop(task.task_id, None)
            self._completed_tasks.clear()
            return count
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                **self._stats,
                "queue_size": len(self._queue),
                "max_size": self.config.max_size,
                "current_task": self._current_task.task_id if self._current_task else None,
                "completed_count": len(self._completed_tasks),
            }
    
    def start_processing(self) -> None:
        """Start the queue processor."""
        if self._running:
            return
        
        if not self._processor:
            raise QueueError("No processor set")
        
        self._running = True
        logger.info("Task queue processing started")
    
    def stop_processing(self) -> None:
        """Stop the queue processor."""
        self._running = False
        with self._condition:
            self._condition.notify_all()
        logger.info("Task queue processing stopped")
    
    def process_sync(self) -> None:
        """Process tasks synchronously (blocking)."""
        self.start_processing()
        
        while self._running:
            try:
                task = self.dequeue(timeout=1.0)
                if task and self._processor:
                    try:
                        result = self._processor(task)
                        self.complete_task(task.task_id, success=True)
                    except Exception as e:
                        self.complete_task(task.task_id, success=False, error=str(e))
            except Exception as e:
                logger.error(f"Error processing task: {e}")
    
    async def process_async(self) -> None:
        """Process tasks asynchronously."""
        self.start_processing()
        
        while self._running:
            try:
                task = self.dequeue(timeout=1.0)
                if task and self._processor:
                    try:
                        if asyncio.iscoroutinefunction(self._processor):
                            await self._processor(task)
                        else:
                            self._processor(task)
                        self.complete_task(task.task_id, success=True)
                    except Exception as e:
                        self.complete_task(task.task_id, success=False, error=str(e))
            except Exception as e:
                logger.error(f"Error processing task: {e}")
                await asyncio.sleep(0.1)
