"""Code Executor module with OpenCode integration."""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import requests

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


@dataclass
class Interaction:
    """An interaction request from OpenCode."""
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
    status: str = "pending"  # pending, running, completed, failed
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
    mode: str = "remote"  # local or remote
    timeout: int = 3600  # 1 hour
    interaction_timeout: int = 1800  # 30 minutes
    max_retries: int = 3
    retry_delay: int = 60
    work_dir: str = "./workspace"
    cli_path: str = "opencode"
    api_url: str = ""
    api_key: str = ""
    forbidden_paths: List[str] = field(default_factory=lambda: ["/etc", "/root", "/sys", "/proc"])
    allowed_commands: List[str] = field(default_factory=lambda: ["create", "modify", "read", "execute"])


class CodeExecutor:
    """
    Code Executor for running OpenCode.
    
    Features:
    - Local CLI and Remote API modes
    - Security checks
    - Timeout handling
    - Interaction support
    - Progress tracking
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
    
    def on_interaction(self, callback: Callable[[str, Interaction], str]) -> None:
        """Set callback for handling interactions."""
        self._on_interaction = callback
    
    def on_progress(self, callback: Callable[[str, int, List[ExecutionStep]], None]) -> None:
        """Set callback for progress updates."""
        self._on_progress = callback
    
    def _check_security(self, instruction: str) -> bool:
        """
        Check instruction for security violations.
        
        Args:
            instruction: The instruction to check
            
        Returns:
            True if safe
            
        Raises:
            SecurityViolationError: If instruction is unsafe
        """
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
    
    def _execute_local(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute instruction using local CLI."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        self._current_execution = result
        
        try:
            cmd = [
                self.config.cli_path,
                "--work-dir", self.config.work_dir,
                instruction,
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=self.config.timeout)
                
                result.stdout = stdout
                result.stderr = stderr
                result.exit_code = process.returncode
                result.success = process.returncode == 0
                result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
                
            except subprocess.TimeoutExpired:
                process.kill()
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = f"Execution timed out after {self.config.timeout}s"
                self._stats["timeout"] += 1
                
        except FileNotFoundError:
            result.status = ExecutionStatus.FAILED
            result.error_message = f"OpenCode CLI not found: {self.config.cli_path}"
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            
        finally:
            result.duration = time.time() - start_time
            self._current_execution = None
        
        return result
    
    def _execute_remote(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute instruction using remote API."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        self._current_execution = result
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            }
            
            payload = {
                "task_id": task_id,
                "instruction": instruction,
                "timeout": self.config.timeout,
                "work_dir": self.config.work_dir,
            }
            
            response = requests.post(
                f"{self.config.api_url}/execute",
                headers=headers,
                json=payload,
                timeout=self.config.timeout + 60,
            )
            
            if response.status_code != 200:
                raise ExecutionError(f"API returned {response.status_code}")
            
            data = response.json()
            
            result.success = data.get("success", False)
            result.stdout = data.get("stdout", "")
            result.stderr = data.get("stderr", "")
            result.exit_code = data.get("exit_code", 0)
            result.repo_url = data.get("repo_url")
            result.files_created = data.get("files_created", [])
            result.files_modified = data.get("files_modified", [])
            result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
            
            if "steps" in data:
                result.steps = [
                    ExecutionStep(
                        name=s.get("name", ""),
                        status=s.get("status", "pending"),
                        output=s.get("output"),
                        error=s.get("error"),
                    )
                    for s in data["steps"]
                ]
            
        except requests.Timeout:
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = f"API request timed out after {self.config.timeout}s"
            self._stats["timeout"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            
        finally:
            result.duration = time.time() - start_time
            self._current_execution = None
        
        return result
    
    async def _handle_interaction(self, task_id: str, interaction: Interaction) -> str:
        """Handle an interaction request."""
        if self._on_interaction:
            return self._on_interaction(task_id, interaction)
        
        if interaction.default:
            return interaction.default
        
        raise InteractionTimeoutError(f"No interaction handler for task {task_id}")
    
    def execute(
        self,
        instruction: str,
        task_id: str,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """
        Execute an instruction.
        
        Args:
            instruction: The instruction to execute
            task_id: Task identifier
            dry_run: If True, don't actually execute
            
        Returns:
            ExecutionResult
        """
        self._stats["total_executions"] += 1
        
        self._check_security(instruction)
        
        if dry_run:
            return ExecutionResult(
                task_id=task_id,
                success=True,
                status=ExecutionStatus.COMPLETED,
                stdout="[DRY RUN] Would execute: " + instruction[:100],
                duration=0.0,
            )
        
        logger.info(f"Executing instruction for task {task_id}")
        
        for attempt in range(self.config.max_retries):
            if self.config.mode == "local":
                result = self._execute_local(instruction, task_id)
            else:
                result = self._execute_remote(instruction, task_id)
            
            if result.success:
                self._stats["successful"] += 1
                return result
            
            if result.status == ExecutionStatus.TIMEOUT:
                break
            
            if attempt < self.config.max_retries - 1:
                logger.warning(f"Execution failed, retrying ({attempt + 1}/{self.config.max_retries})")
                time.sleep(self.config.retry_delay)
        
        self._stats["failed"] += 1
        return result
    
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


class OpenCodeClient:
    """
    High-level client for OpenCode interactions.
    """
    
    def __init__(self, executor: CodeExecutor):
        self.executor = executor
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, task_id: str, instruction: str) -> str:
        """Create a new execution session."""
        session_id = f"session_{task_id}"
        self._sessions[session_id] = {
            "task_id": task_id,
            "instruction": instruction,
            "status": "created",
            "created_at": datetime.now(timezone.utc),
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session info."""
        return self._sessions.get(session_id)
    
    def close_session(self, session_id: str) -> None:
        """Close a session."""
        self._sessions.pop(session_id, None)
