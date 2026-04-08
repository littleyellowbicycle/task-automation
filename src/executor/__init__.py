"""Code Executor module with abstract interface for multiple backends."""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import webbrowser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

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


class OpenCodeExecutor(BaseExecutor):
    """
    OpenCode executor implementation.
    
    Supports modes:
    - webui: Open browser for manual interaction
    - cli: Command line execution
    - attach: Attach to running server
    """
    
    @property
    def name(self) -> str:
        return "OpenCode"
    
    @property
    def supported_modes(self) -> List[str]:
        return ["webui", "cli", "attach"]
    
    def health_check(self) -> bool:
        """Check if OpenCode is available."""
        if self.config.mode == "webui":
            if self.config.web_url:
                try:
                    resp = requests.get(f"{self.config.web_url}/health", timeout=5)
                    return resp.status_code == 200
                except:
                    return False
        elif self.config.mode == "cli":
            try:
                result = subprocess.run(
                    [self.config.cli_path or "opencode", "--version"],
                    capture_output=True,
                    timeout=10,
                )
                return result.returncode == 0
            except:
                return False
        return False
    
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        """Get OpenCode web UI URL."""
        return self.config.web_url or None
    
    def execute(self, instruction: str, task_id: str, dry_run: bool = False) -> ExecutionResult:
        """Execute instruction using OpenCode."""
        self._stats["total_executions"] += 1
        self._check_security(instruction)
        
        if dry_run:
            return ExecutionResult(
                task_id=task_id,
                success=True,
                status=ExecutionStatus.COMPLETED,
                stdout=f"[DRY RUN] Would execute via {self.name}: " + instruction[:100],
                duration=0.0,
            )
        
        logger.info(f"Executing via {self.name} for task {task_id}")
        
        if self.config.mode == "webui":
            return self._execute_webui(instruction, task_id)
        elif self.config.mode == "cli":
            return self._execute_cli(instruction, task_id)
        elif self.config.mode == "attach":
            return self._execute_attach(instruction, task_id)
        else:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                status=ExecutionStatus.FAILED,
                error_message=f"Unsupported mode: {self.config.mode}",
            )
    
    def _execute_webui(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via Web UI - opens browser for user interaction."""
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.WAITING_INPUT,
        )
        
        web_url = self.config.web_url
        if not web_url:
            result.error_message = "Web UI URL not configured"
            result.status = ExecutionStatus.FAILED
            return result
        
        logger.info(f"Opening OpenCode Web UI: {web_url}")
        logger.info(f"Task instruction: {instruction}")
        
        webbrowser.open(web_url)
        
        result.metadata["web_url"] = web_url
        result.metadata["instruction"] = instruction
        result.metadata["message"] = "Please complete the task in the OpenCode Web UI"
        
        self._stats["successful"] += 1
        return result
    
    def _execute_cli(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via CLI."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        self._current_execution = result
        
        try:
            cmd = [self.config.cli_path or "opencode", "run", "--dir", self.config.work_dir, instruction]
            
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
                
                if result.success:
                    self._stats["successful"] += 1
                else:
                    self._stats["failed"] += 1
                
            except subprocess.TimeoutExpired:
                process.kill()
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = f"Execution timed out after {self.config.timeout}s"
                self._stats["timeout"] += 1
                
        except FileNotFoundError:
            result.status = ExecutionStatus.FAILED
            result.error_message = f"OpenCode CLI not found: {self.config.cli_path}"
            self._stats["failed"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1
            
        finally:
            result.duration = time.time() - start_time
            self._current_execution = None
        
        return result
    
    def _execute_attach(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute by attaching to running server."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        try:
            cmd = [
                self.config.cli_path or "opencode", "run",
                "--attach", self.config.web_url,
                "--dir", self.config.work_dir,
                instruction,
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            stdout, stderr = process.communicate(timeout=self.config.timeout)
            
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = process.returncode
            result.success = process.returncode == 0
            result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
            
            if result.success:
                self._stats["successful"] += 1
            else:
                self._stats["failed"] += 1
                
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1
            
        finally:
            result.duration = time.time() - start_time
        
        return result


class OpenHandsExecutor(BaseExecutor):
    """
    OpenHands executor implementation.
    
    OpenHands (formerly OpenDevin) is an AI-driven multi-intelligent agent 
    assistant for software development.
    
    Supports modes:
    - webui: Open browser for manual interaction
    - cli: Command line execution via openhands CLI
    - api: HTTP API calls to OpenHands server
    """
    
    @property
    def name(self) -> str:
        return "OpenHands"
    
    @property
    def supported_modes(self) -> List[str]:
        return ["webui", "cli", "api"]
    
    def health_check(self) -> bool:
        """Check if OpenHands is available."""
        if self.config.mode == "webui" or self.config.mode == "api":
            if self.config.api_url:
                try:
                    resp = requests.get(f"{self.config.api_url}/health", timeout=5)
                    return resp.status_code == 200
                except:
                    return False
        elif self.config.mode == "cli":
            try:
                result = subprocess.run(
                    [self.config.cli_path or "openhands", "--version"],
                    capture_output=True,
                    timeout=10,
                )
                return result.returncode == 0
            except:
                return False
        return False
    
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        """Get OpenHands web UI URL."""
        return self.config.web_url or self.config.api_url
    
    def execute(self, instruction: str, task_id: str, dry_run: bool = False) -> ExecutionResult:
        """Execute instruction using OpenHands."""
        self._stats["total_executions"] += 1
        self._check_security(instruction)
        
        if dry_run:
            return ExecutionResult(
                task_id=task_id,
                success=True,
                status=ExecutionStatus.COMPLETED,
                stdout=f"[DRY RUN] Would execute via {self.name}: " + instruction[:100],
                duration=0.0,
            )
        
        logger.info(f"Executing via {self.name} for task {task_id}")
        
        if self.config.mode == "webui":
            return self._execute_webui(instruction, task_id)
        elif self.config.mode == "cli":
            return self._execute_cli(instruction, task_id)
        elif self.config.mode == "api":
            return self._execute_api(instruction, task_id)
        else:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                status=ExecutionStatus.FAILED,
                error_message=f"Unsupported mode: {self.config.mode}",
            )
    
    def _execute_webui(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via Web UI - opens browser for user interaction."""
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.WAITING_INPUT,
        )
        
        web_url = self.config.web_url or self.config.api_url
        if not web_url:
            result.error_message = "Web UI URL not configured"
            result.status = ExecutionStatus.FAILED
            return result
        
        logger.info(f"Opening OpenHands Web UI: {web_url}")
        logger.info(f"Task instruction: {instruction}")
        
        webbrowser.open(web_url)
        
        result.metadata["web_url"] = web_url
        result.metadata["instruction"] = instruction
        result.metadata["message"] = "Please complete the task in the OpenHands Web UI"
        
        self._stats["successful"] += 1
        return result
    
    def _execute_cli(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via OpenHands CLI."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        self._current_execution = result
        
        try:
            cli_path = self.config.cli_path or "openhands"
            work_dir = self.config.work_dir
            
            cmd = [
                cli_path,
                "-t", instruction,
                "-d", work_dir,
            ]
            
            logger.info(f"Running OpenHands CLI: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=work_dir,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=self.config.timeout)
                
                result.stdout = stdout
                result.stderr = stderr
                result.exit_code = process.returncode
                result.success = process.returncode == 0
                result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
                
                if result.success:
                    self._stats["successful"] += 1
                else:
                    self._stats["failed"] += 1
                
            except subprocess.TimeoutExpired:
                process.kill()
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = f"Execution timed out after {self.config.timeout}s"
                self._stats["timeout"] += 1
                
        except FileNotFoundError:
            result.status = ExecutionStatus.FAILED
            result.error_message = f"OpenHands CLI not found: {self.config.cli_path}"
            self._stats["failed"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1
            
        finally:
            result.duration = time.time() - start_time
            self._current_execution = None
        
        return result
    
    def _execute_api(self, instruction: str, task_id: str) -> ExecutionResult:
        """Execute via OpenHands HTTP API."""
        start_time = time.time()
        
        result = ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.RUNNING,
        )
        
        try:
            api_url = self.config.api_url
            if not api_url:
                result.status = ExecutionStatus.FAILED
                result.error_message = "API URL not configured"
                self._stats["failed"] += 1
                return result
            
            headers = {
                "Content-Type": "application/json",
            }
            
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            payload = {
                "task": instruction,
                "task_id": task_id,
                "work_dir": self.config.work_dir,
            }
            
            logger.info(f"Calling OpenHands API: {api_url}")
            
            response = requests.post(
                f"{api_url}/api/task",
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
            )
            
            result.exit_code = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                result.success = True
                result.status = ExecutionStatus.COMPLETED
                result.stdout = data.get("output", "")
                result.metadata["result"] = data
                self._stats["successful"] += 1
            else:
                result.status = ExecutionStatus.FAILED
                result.error_message = f"API error: {response.status_code} - {response.text[:500]}"
                self._stats["failed"] += 1
                
        except requests.exceptions.Timeout:
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = f"API request timed out after {self.config.timeout}s"
            self._stats["timeout"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            self._stats["failed"] += 1
            
        finally:
            result.duration = time.time() - start_time
        
        return result


class OpenClawExecutor(BaseExecutor):
    """
    OpenClaw executor implementation.
    
    OpenClaw is an automation task tool with multi-model support.
    """
    
    @property
    def name(self) -> str:
        return "OpenClaw"
    
    @property
    def supported_modes(self) -> List[str]:
        return ["cli", "api"]
    
    def health_check(self) -> bool:
        if self.config.cli_path:
            try:
                result = subprocess.run(
                    [self.config.cli_path, "--version"],
                    capture_output=True,
                    timeout=10,
                )
                return result.returncode == 0
            except:
                return False
        return False
    
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        return self.config.web_url
    
    def execute(self, instruction: str, task_id: str, dry_run: bool = False) -> ExecutionResult:
        self._stats["total_executions"] += 1
        self._check_security(instruction)
        
        if dry_run:
            return ExecutionResult(
                task_id=task_id,
                success=True,
                status=ExecutionStatus.COMPLETED,
                stdout=f"[DRY RUN] Would execute via {self.name}: " + instruction[:100],
                duration=0.0,
            )
        
        logger.info(f"Executing via {self.name} for task {task_id}")
        
        return ExecutionResult(
            task_id=task_id,
            success=False,
            status=ExecutionStatus.FAILED,
            error_message=f"OpenClaw executor not yet implemented",
        )


EXECUTOR_REGISTRY: Dict[str, Type[BaseExecutor]] = {
    "opencode": OpenCodeExecutor,
    "openhands": OpenHandsExecutor,
    "openclaw": OpenClawExecutor,
}


def create_executor(config: Optional[ExecutorConfig] = None) -> BaseExecutor:
    """
    Factory function to create an executor based on configuration.
    
    Args:
        config: Executor configuration
        
    Returns:
        BaseExecutor instance
    """
    config = config or ExecutorConfig.from_env()
    
    backend = config.backend.lower()
    
    if backend not in EXECUTOR_REGISTRY:
        raise ExecutorNotAvailableError(
            f"Unknown executor backend: {backend}. "
            f"Available: {list(EXECUTOR_REGISTRY.keys())}"
        )
    
    executor_class = EXECUTOR_REGISTRY[backend]
    return executor_class(config)


class CodeExecutor:
    """
    High-level executor interface for backward compatibility.
    
    This class wraps the new abstract executor system.
    """
    
    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig.from_env()
        self._executor = create_executor(self.config)
    
    @property
    def executor(self) -> BaseExecutor:
        """Get the underlying executor instance."""
        return self._executor
    
    def execute(
        self,
        instruction: str,
        task_id: str,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Execute an instruction."""
        return self._executor.execute(instruction, task_id, dry_run)
    
    def health_check(self) -> bool:
        """Check if executor is available."""
        return self._executor.health_check()
    
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        """Get web UI URL."""
        return self._executor.get_web_url(task_id)
    
    def on_interaction(self, callback: Callable[[str, Interaction], str]) -> None:
        """Set interaction callback."""
        self._executor.on_interaction(callback)
    
    def on_progress(self, callback: Callable[[str, int, List[ExecutionStep]], None]) -> None:
        """Set progress callback."""
        self._executor.on_progress(callback)
    
    def cancel(self, task_id: str) -> bool:
        """Cancel execution."""
        return self._executor.cancel(task_id)
    
    def get_status(self, task_id: str) -> Optional[ExecutionStatus]:
        """Get execution status."""
        return self._executor.get_status(task_id)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return self._executor.stats
    
    async def execute_async(
        self,
        instruction: str,
        task_id: str,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Execute asynchronously."""
        return await self._executor.execute_async(instruction, task_id, dry_run)
