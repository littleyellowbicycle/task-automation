from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ListenerMessageRequest(BaseModel):
    msg_id: str = ""
    content: str
    sender_id: str = "unknown"
    sender_name: str = "unknown"
    conversation_id: str = "unknown"
    conversation_type: str = "private"
    timestamp: str = ""
    msg_type: str = "text"
    platform: str = "wework"
    listener_type: str = "unknown"


class AnalysisDoneRequest(BaseModel):
    task_id: str
    is_task: bool = True
    summary: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    core_features: List[str] = Field(default_factory=list)
    complexity: str = "simple"
    category: Optional[str] = None
    reason: Optional[str] = None


class DecisionRequest(BaseModel):
    task_id: str
    action: str
    user_id: Optional[str] = None
    timestamp: str = ""


class ExecutionDoneRequest(BaseModel):
    task_id: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    repo_url: Optional[str] = None
    files_created: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    duration: float = 0.0
    error_message: Optional[str] = None


class ExecutionProgressRequest(BaseModel):
    task_id: str
    progress: int = 0
    current_step: str = ""
    steps: list = Field(default_factory=list)


class RecordingDoneRequest(BaseModel):
    task_id: str
    record_id: Optional[str] = None
    success: bool = True
