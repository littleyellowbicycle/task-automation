"""
Base Executor module with abstract interface.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
import webbrowser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("executor")


class ExecutorError(WeChatAutomationError):
    """Base exception for executor errors."""
    pass


class ExecutionError(ExecutorError):
    """Raised when execution fails."""
    pass


class SecurityViolationError(ExecutorError):
    """Raised when a security check fails."""
    pass


class InteractionTimeoutError(ExecutorError):
    """Raised when interaction times out."""
    pass


class ExecutorNotAvailableError(ExecutorError):
    """Raised when executor backend is not available."""
    pass


class ExecutionStatus(str, Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class InteractionType(str, Enum):
    """Types of user interactions."""
    CONFIRMATION = "confirmation"
    CHOICE = "choice"
    INPUT = "input"
    FILE_SELECTION = "file_selection"
    ERROR_HANDLING = "error_handling"


class ExecutorType(str, Enum):
    """Supported executor backends."""
    OPENCODE = "opencode"
    OPENHANDS = "openhands"
    OPENCLAW = "openclaw"
    CUSTOM = "custom"


@dataclass
class Interaction:
    """An interaction request from executor."""
    id: str
    type: InteractionType
    question: str
    options: Optional[List[str]] = None
    default: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionStep:
    """A step in the execution process."""
    name: str
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of code execution."""
    task_id: str
    success: bool
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    repo_url: Optional[str] = None
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    steps: List[ExecutionStep] = field(default_factory=list)
    interactions: List[Interaction] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutorConfig:
    """Configuration for code executor."""
    backend: str = "opencode"
    mode: str = "webui"
    timeout: int = 3600
    interaction_timeout: int = 1800
    max_retries: int = 3
    retry_delay: int = 60
    work_dir: str = "./workspace"
    web_url: str = ""
    api_url: str = ""
    api_key: str = ""
    cli_path: str = ""
    model_provider: str = "opencode"
    model_id: str = "minimax-m2.5-free"
    forbidden_paths: List[str] = field(default_factory=lambda: ["/etc", "/root", "/sys", "/proc"])
    
    @classmethod
    def from_env(cls) -> "ExecutorConfig":
        """Create config from environment variables."""
        import os
        return cls(
            backend=os.getenv("EXECUTOR_BACKEND", "opencode"),
            mode=os.getenv("EXECUTOR_MODE", "webui"),
            web_url=os.getenv("EXECUTOR_WEB_URL", ""),
            api_url=os.getenv("EXECUTOR_API_URL", ""),
            api_key=os.getenv("EXECUTOR_API_KEY", ""),
            cli_path=os.getenv("EXECUTOR_CLI_PATH", ""),
            timeout=int(os.getenv("EXECUTOR_TIMEOUT", "3600")),
            work_dir=os.getenv("EXECUTOR_WORK_DIR", "./workspace"),
            model_provider=os.getenv("EXECUTOR_MODEL_PROVIDER", "opencode"),
            model_id=os.getenv("EXECUTOR_MODEL_ID", "minimax-m2.5-free"),
        )


class BaseExecutor(ABC):
    """
    Abstract base class for code executors.
    
    Supports multiple backends: OpenCode, OpenHands, OpenClaw, etc.
    """
    
    FORBIDDEN_PATTERNS = [
        "rm -rf",
        "sudo",
        "chmod 777",
        "> /dev/sd",
        "mkfs",
        "dd if=",
        ":(){ :|:& };:",
        "curl | bash",
        "wget | bash",
    ]
    
    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig()
        self._current_execution: Optional[ExecutionResult] = None
        self._on_interaction: Optional[Callable[[str, Interaction], str]] = None
        self._on_progress: Optional[Callable[[str, int, List[ExecutionStep]], None]] = None
        self._stats = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "timeout": 0,
            "cancelled": 0,
        }
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return executor name."""
        pass
    
    @property
    @abstractmethod
    def supported_modes(self) -> List[str]:
        """Return supported execution modes."""
        pass
    
    @abstractmethod
    def execute(self, instruction: str, task_id: str, dry_run: bool = False) -> ExecutionResult:
        """
        Execute an instruction.
        
        Args:
            instruction: The instruction to execute
            task_id: Task identifier
            dry_run: If True, don't actually execute
            
        Returns:
            ExecutionResult
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if executor is available."""
        pass
    
    @abstractmethod
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        """Get web UI URL for manual interaction."""
        pass
    
    def on_interaction(self, callback: Callable[[str, Interaction], str]) -> None:
        """Set callback for handling interactions."""
        self._on_interaction = callback
    
    def on_progress(self, callback: Callable[[str, int, List[ExecutionStep]], None]) -> None:
        """Set callback for progress updates."""
        self._on_progress = callback
    
    def _check_security(self, instruction: str) -> bool:
        """Check instruction for security violations."""
        instruction_lower = instruction.lower()
        
        for forbidden in self.config.forbidden_paths:
            if forbidden.lower() in instruction_lower:
                raise SecurityViolationError(
                    f"Instruction contains forbidden path: {forbidden}"
                )
        
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in instruction_lower:
                raise SecurityViolationError(
                    f"Instruction contains forbidden pattern: {pattern}"
                )
        
        return True
    
    def cancel(self, task_id: str) -> bool:
        """Cancel a running execution."""
        if self._current_execution and self._current_execution.task_id == task_id:
            self._current_execution.status = ExecutionStatus.CANCELLED
            self._stats["cancelled"] += 1
            logger.info(f"Execution cancelled for task {task_id}")
            return True
        return False
    
    def get_status(self, task_id: str) -> Optional[ExecutionStatus]:
        """Get the status of an execution."""
        if self._current_execution and self._current_execution.task_id == task_id:
            return self._current_execution.status
        return None
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            **self._stats,
            "current_execution": self._current_execution.task_id if self._current_execution else None,
        }
    
    async def execute_async(
        self,
        instruction: str,
        task_id: str,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Execute an instruction asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute(instruction, task_id, dry_run),
        )
