"""Task record models for Feishu."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"           # Awaiting user confirmation
    APPROVED = "approved"         # User approved, ready to execute
    EXECUTING = "executing"       # Currently executing
    COMPLETED = "completed"       # Successfully completed
    FAILED = "failed"             # Execution failed
    CANCELLED = "cancelled"       # User cancelled
    TIMEOUT = "timeout"           # Confirmation timeout


@dataclass
class TaskRecord:
    """Task record for Feishu bitable."""
    task_id: str
    raw_message: str
    summary: str = ""
    tech_stack: List[str] = field(default_factory=list)
    core_features: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    estimated_complexity: str = "medium"
    status: TaskStatus = TaskStatus.PENDING
    code_repo_url: Optional[str] = None
    executor_result: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Feishu API."""
        return {
            "task_id": self.task_id,
            "raw_message": self.raw_message,
            "summary": self.summary,
            "tech_stack": ",".join(self.tech_stack),
            "core_features": ",".join(self.core_features),
            "constraints": ",".join(self.constraints),
            "estimated_complexity": self.estimated_complexity,
            "status": self.status.value,
            "code_repo_url": self.code_repo_url or "",
            "executor_result": self.executor_result or "",
            "error_message": self.error_message or "",
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else "",
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
            "user_id": self.user_id or "",
            "user_name": self.user_name or "",
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskRecord":
        """Create from dictionary."""
        return cls(
            task_id=data.get("task_id", ""),
            raw_message=data.get("raw_message", ""),
            summary=data.get("summary", ""),
            tech_stack=data.get("tech_stack", "").split(",") if data.get("tech_stack") else [],
            core_features=data.get("core_features", "").split(",") if data.get("core_features") else [],
            constraints=data.get("constraints", "").split(",") if data.get("constraints") else [],
            estimated_complexity=data.get("estimated_complexity", "medium"),
            status=TaskStatus(data.get("status", "pending")),
            code_repo_url=data.get("code_repo_url") or None,
            executor_result=data.get("executor_result") or None,
            error_message=data.get("error_message") or None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            confirmed_at=datetime.fromisoformat(data["confirmed_at"]) if data.get("confirmed_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            user_id=data.get("user_id") or None,
            user_name=data.get("user_name") or None,
        )
