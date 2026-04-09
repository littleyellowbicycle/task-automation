"""
Code Executor module with abstract interface for multiple backends.

Supported backends:
- OpenCode: AI-powered coding agent with SDK support
- OpenHands: AI-driven software development agent
- OpenClaw: Automation task tool

Usage:
    from src.executor import CodeExecutor, ExecutorConfig
    
    config = ExecutorConfig(backend="opencode", mode="api")
    executor = CodeExecutor(config)
    result = executor.execute("Create a hello.py file", "task_001")
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from .base import (
    BaseExecutor,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    ExecutorConfig,
    ExecutorError,
    ExecutorNotAvailableError,
    ExecutorType,
    Interaction,
    InteractionTimeoutError,
    InteractionType,
    SecurityViolationError,
)
from .opencode import OpenCodeExecutor
from .openhands import OpenHandsExecutor

logger = __import__("src.utils").utils.get_logger("executor")

EXECUTOR_REGISTRY: Dict[str, Type[BaseExecutor]] = {
    "opencode": OpenCodeExecutor,
    "openhands": OpenHandsExecutor,
}


def create_executor(config: Optional[ExecutorConfig] = None) -> BaseExecutor:
    """
    Factory function to create an executor based on configuration.
    
    Args:
        config: Executor configuration. If not provided, loads from environment.
        
    Returns:
        BaseExecutor instance
        
    Raises:
        ExecutorNotAvailableError: If the backend is not registered
        
    Example:
        config = ExecutorConfig(backend="opencode", mode="api")
        executor = create_executor(config)
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
    High-level executor interface.
    
    This class provides a unified interface for executing tasks
    across different backends (OpenCode, OpenHands, etc.).
    
    Example:
        executor = CodeExecutor()
        
        # Dry run
        result = executor.execute("Create hello.py", "task_001", dry_run=True)
        
        # Real execution
        result = executor.execute("Create hello.py", "task_001")
        
        # Check status
        status = executor.get_status("task_001")
    """
    
    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig.from_env()
        self._executor = create_executor(self.config)
    
    @property
    def executor(self) -> BaseExecutor:
        """Get the underlying executor instance."""
        return self._executor
    
    @property
    def name(self) -> str:
        """Get executor name."""
        return self._executor.name
    
    @property
    def supported_modes(self) -> List[str]:
        """Get supported modes."""
        return self._executor.supported_modes
    
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
            task_id: Unique task identifier
            dry_run: If True, simulate execution without running
            
        Returns:
            ExecutionResult with status, output, and metadata
        """
        return self._executor.execute(instruction, task_id, dry_run)
    
    def health_check(self) -> bool:
        """Check if executor backend is available."""
        return self._executor.health_check()
    
    def get_web_url(self, task_id: Optional[str] = None) -> Optional[str]:
        """Get web UI URL for manual interaction."""
        return self._executor.get_web_url(task_id)
    
    def on_interaction(self, callback) -> None:
        """Set callback for handling interactions."""
        self._executor.on_interaction(callback)
    
    def on_progress(self, callback) -> None:
        """Set callback for progress updates."""
        self._executor.on_progress(callback)
    
    def cancel(self, task_id: str) -> bool:
        """Cancel a running execution."""
        return self._executor.cancel(task_id)
    
    def get_status(self, task_id: str) -> Optional[ExecutionStatus]:
        """Get execution status."""
        return self._executor.get_status(task_id)
    
    @property
    def stats(self) -> dict:
        """Get executor statistics."""
        return self._executor.stats
    
    async def execute_async(
        self,
        instruction: str,
        task_id: str,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Execute asynchronously."""
        return await self._executor.execute_async(instruction, task_id, dry_run)


__all__ = [
    "BaseExecutor",
    "CodeExecutor",
    "ExecutionError",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionStep",
    "ExecutorConfig",
    "ExecutorError",
    "ExecutorNotAvailableError",
    "ExecutorType",
    "Interaction",
    "InteractionTimeoutError",
    "InteractionType",
    "OpenCodeExecutor",
    "OpenHandsExecutor",
    "SecurityViolationError",
    "create_executor",
]
