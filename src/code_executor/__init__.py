"""OpenCode executor wrapper for code generation."""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from ..utils import get_logger
from ..exceptions import SecurityViolationError

logger = get_logger("code_executor")


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    is_timeout: bool = False
    repo_url: Optional[str] = None


class CodeExecutor:
    """
    Executor that wraps OpenCode CLI for code generation.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 18792,
        work_dir: str = "/tmp/opencode_workspace",
        timeout: int = 600,
        allowed_commands: Optional[List[str]] = None,
        forbidden_paths: Optional[List[str]] = None,
    ):
        """
        Initialize code executor.
        
        Args:
            host: OpenCode server host
            port: OpenCode server port
            work_dir: Working directory for code generation
            timeout: Execution timeout in seconds
            allowed_commands: Allowed command types
            forbidden_paths: Paths that cannot be modified
        """
        self.host = host
        self.port = port
        self.work_dir = work_dir
        self.timeout = timeout
        self.allowed_commands = allowed_commands or ["create", "modify", "read"]
        self.forbidden_paths = forbidden_paths or ["/etc", "/root", "/sys", "/proc"]
        self._ensure_workdir()
    
    def _ensure_workdir(self):
        """Ensure working directory exists."""
        Path(self.work_dir).mkdir(parents=True, exist_ok=True)
    
    def _check_security(self, instruction: str) -> bool:
        """
        Check if instruction is safe to execute.
        
        Args:
            instruction: Instruction to check
            
        Returns:
            True if safe
            
        Raises:
            SecurityViolationError: If instruction is not safe
        """
        instruction_lower = instruction.lower()
        
        # Check for forbidden paths
        for forbidden in self.forbidden_paths:
            if forbidden in instruction_lower:
                raise SecurityViolationError(f"Instruction contains forbidden path: {forbidden}")
        
        return True
    
    async def execute(self, instruction: str, dry_run: bool = False) -> ExecutionResult:
        """
        Execute OpenCode instruction.
        
        Args:
            instruction: Natural language instruction
            dry_run: If True, don't actually execute
            
        Returns:
            ExecutionResult
        """
        import time
        start_time = time.time()
        
        if dry_run:
            logger.info(f"[DRY RUN] Would execute: {instruction}")
            return ExecutionResult(
                success=True,
                exit_code=0,
                stdout=f"[DRY RUN] {instruction}",
                stderr="",
                duration=0,
            )
        
        # Security check
        self._check_security(instruction)
        
        try:
            # Try OpenCode CLI first
            cmd = [
                "opencode",
                "--host", self.host,
                "--port", str(self.port),
                instruction,
            ]
            
            logger.info(f"Executing OpenCode: {instruction[:50]}...")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.work_dir,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
                
                duration = time.time() - start_time
                success = process.returncode == 0
                
                result = ExecutionResult(
                    success=success,
                    exit_code=process.returncode,
                    stdout=stdout.decode() if stdout else "",
                    stderr=stderr.decode() if stderr else "",
                    duration=duration,
                )
                
                if success:
                    logger.info(f"OpenCode execution successful ({duration:.1f}s)")
                else:
                    logger.error(f"OpenCode execution failed: {stderr.decode()[:200]}")
                
                return result
                
            except asyncio.TimeoutError:
                process.kill()
                duration = time.time() - start_time
                logger.error(f"OpenCode execution timed out after {self.timeout}s")
                
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {self.timeout} seconds",
                    duration=duration,
                    is_timeout=True,
                )
                
        except FileNotFoundError:
            # OpenCode CLI not found, try API mode
            logger.warning("OpenCode CLI not found, falling back to API mode")
            return await self._execute_via_api(instruction, start_time)
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"OpenCode execution error: {e}")
            
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
            )
    
    async def _execute_via_api(self, instruction: str, start_time: float) -> ExecutionResult:
        """Execute via OpenCode API instead of CLI."""
        # This would use the OpenCode API directly
        # For now, return an error indicating API mode not implemented
        duration = time.time() - start_time
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr="OpenCode CLI not available and API mode not implemented",
            duration=duration,
        )
    
    def extract_repo_url(self, output: str) -> Optional[str]:
        """
        Extract repository URL from execution output.
        
        Args:
            output: Execution output
            
        Returns:
            Repository URL if found
        """
        # Look for common URL patterns
        patterns = [
            r'https?://github\.com/[^\s]+',
            r'https?://gitlab\.com/[^\s]+',
            r'file:///[^\s]+',
        ]
        
        for pattern in patterns:
            import re
            match = re.search(pattern, output)
            if match:
                return match.group()
        
        return None
