from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import List, Optional


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class TaskRecord:
    task_id: str
    raw_message: str
    summary: str
    tech_stack: List[str]
    core_features: List[str]
    status: TaskStatus  # e.g., PENDING, APPROVED, EXECUTING, COMPLETED, FAILED
    code_repo_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        now = datetime.utcnow()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
