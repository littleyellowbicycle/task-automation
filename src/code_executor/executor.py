from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CodeExecutor:
    """Asynchronous wrapper around shell execution to generate/modify code."""

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = int(timeout)

    async def execute(self, command: str) -> ExecutionResult:
        # Execute a shell command asynchronously and capture output
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                exit_code = proc.returncode if proc.returncode is not None else -1
            except asyncio.TimeoutError:
                proc.kill()
                stdout, stderr = await proc.communicate()
                exit_code = -1
                return ExecutionResult(exit_code, stdout.decode(), stderr.decode(), timed_out=True)
            return ExecutionResult(exit_code, stdout.decode(), stderr.decode())
        except FileNotFoundError as e:
            return ExecutionResult(-1, "", str(e))
