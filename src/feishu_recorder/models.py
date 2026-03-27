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
    code_repo_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        now = datetime.utcnow()
        if self.tech_stack is None:
            self.tech_stack = []
        if self.core_features is None:
            self.core_features = []
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "raw_message": self.raw_message,
            "summary": self.summary,
            "tech_stack": ",".join(self.tech_stack) if self.tech_stack else "",
            "core_features": ",".join(self.core_features) if self.core_features else "",
            "status": self.status.value,
            "code_repo_url": self.code_repo_url or "",
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskRecord:
        tech_stack = data.get("tech_stack", "").split(",") if data.get("tech_stack") else []
        core_features = data.get("core_features", "").split(",") if data.get("core_features") else []
        return cls(
            task_id=data.get("task_id", ""),
            raw_message=data.get("raw_message", ""),
            summary=data.get("summary", ""),
            tech_stack=tech_stack,
            core_features=core_features,
            status=TaskStatus(data.get("status", "pending")),
        )
