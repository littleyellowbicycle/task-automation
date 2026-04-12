from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    RECEIVED = "received"
    FILTERING = "filtering"
    ANALYZING = "analyzing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTING_WAITING_INPUT = "executing_waiting_input"
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    LATER = "later"


@dataclass
class AnalysisResult:
    is_task: bool = False
    summary: str = ""
    tech_stack: List[str] = field(default_factory=list)
    core_features: List[str] = field(default_factory=list)
    complexity: str = "simple"
    category: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class ExecutionResultData:
    success: bool = False
    stdout: str = ""
    stderr: str = ""
    repo_url: Optional[str] = None
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    duration: float = 0.0
    error_message: Optional[str] = None


@dataclass
class RecordingResultData:
    success: bool = False
    record_id: Optional[str] = None


@dataclass
class TaskState:
    task_id: str
    status: TaskStatus
    raw_message: str
    standard_message: Optional[Dict[str, Any]] = None
    analysis_result: Optional[AnalysisResult] = None
    decision: Optional[str] = None
    execution_result: Optional[ExecutionResultData] = None
    recording_result: Optional[RecordingResultData] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_status(self, status: TaskStatus, error: Optional[str] = None) -> None:
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        if error:
            self.error_message = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "raw_message": self.raw_message,
            "summary": self.analysis_result.summary if self.analysis_result else None,
            "decision": self.decision,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }
