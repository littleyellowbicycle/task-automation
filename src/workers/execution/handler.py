from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ...code_executor import CodeExecutor, ExecutionResult
from ...utils import get_logger

logger = get_logger("workers.execution.handler")


class ExecutionHandler:
    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        api_url: str = "http://localhost:4096",
        work_dir: str = "./workspace",
        timeout: int = 600,
        model_provider: str = "opencode",
        model_id: str = "minimax-m2.5-free",
        host: str = "",
        port: int = 0,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.executor = CodeExecutor(
            api_url=api_url,
            work_dir=work_dir,
            timeout=timeout,
            model_provider=model_provider,
            model_id=model_id,
            host=host,
            port=port,
        )

    async def handle_execution_request(
        self,
        task_id: str,
        summary: str,
        raw_message: str = "",
    ) -> Dict[str, Any]:
        instruction = raw_message or summary

        logger.info(f"Executing task {task_id}: {instruction[:50]}...")

        try:
            result = await self.executor.execute(instruction)

            execution_data = {
                "task_id": task_id,
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "repo_url": result.repo_url,
                "files_created": result.files_created,
                "files_modified": result.files_modified,
                "duration": result.duration,
                "error_message": result.stderr if not result.success else None,
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{self.gateway_url}/api/v1/execution/done",
                        json=execution_data,
                    )
            except Exception as e:
                logger.error(f"Failed to callback gateway: {e}")

            return {"code": 0, "action": "executed", "success": result.success}

        except Exception as e:
            logger.error(f"Execution failed for task {task_id}: {e}")

            execution_data = {
                "task_id": task_id,
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "duration": 0,
                "error_message": str(e),
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{self.gateway_url}/api/v1/execution/done",
                        json=execution_data,
                    )
            except Exception as callback_err:
                logger.error(f"Failed to callback gateway: {callback_err}")

            return {"code": 0, "action": "execution_failed"}
