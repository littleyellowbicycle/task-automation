from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import List, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

@dataclass
class TaskRecord:
    task_id: str
    raw_message: str
    summary: str
    tech_stack: List[str] = None
    core_features: List[str] = None
    status: TaskStatus = TaskStatus.PENDING
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    executor_result: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    code_repo_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        from datetime import timezone
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        if self.tech_stack is None:
            self.tech_stack = []
        if self.core_features is None:
            self.core_features = []

    @classmethod
    def from_dict(cls, data: dict) -> "TaskRecord":
        """Create a TaskRecord from a dictionary."""
        # Handle string tech_stack
        tech_stack = data.get("tech_stack", [])
        if isinstance(tech_stack, str):
            tech_stack = [t.strip() for t in tech_stack.split(",") if t.strip()]
        
        return cls(
            task_id=data.get("task_id"),
            raw_message=data.get("raw_message", ""),
            summary=data.get("summary", ""),
            tech_stack=tech_stack,
            core_features=data.get("core_features", []),
            status=TaskStatus(data.get("status", "pending")),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            executor_result=data.get("executor_result"),
            error_message=data.get("error_message"),
            completed_at=data.get("completed_at"),
            code_repo_url=data.get("code_repo_url"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "raw_message": self.raw_message,
            "summary": self.summary,
            "tech_stack": self.tech_stack,
            "core_features": self.core_features,
            "status": self.status.value,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "executor_result": self.executor_result,
            "error_message": self.error_message,
            "completed_at": self.completed_at,
            "code_repo_url": self.code_repo_url,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
