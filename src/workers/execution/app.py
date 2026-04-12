from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .handler import ExecutionHandler
from ...utils import get_logger

logger = get_logger("workers.execution.app")


class ExecutionRequestModel(BaseModel):
    task_id: str
    summary: str
    raw_message: str = ""


def create_execution_app(
    gateway_url: str = "http://localhost:8000",
    port: int = 8003,
    opencode_host: str = "localhost",
    opencode_port: int = 18792,
    work_dir: str = "/tmp/opencode_workspace",
    timeout: int = 600,
) -> FastAPI:
    app = FastAPI(
        title="Execution Worker",
        version="2.0.0",
    )

    handler = ExecutionHandler(
        gateway_url=gateway_url,
        host=opencode_host,
        port=opencode_port,
        work_dir=work_dir,
        timeout=timeout,
    )

    @app.post("/worker/execution/request")
    async def execution_request(request: ExecutionRequestModel):
        result = await handler.handle_execution_request(
            task_id=request.task_id,
            summary=request.summary,
            raw_message=request.raw_message,
        )
        return result

    @app.get("/health")
    async def health():
        return {"status": "healthy", "worker": "execution"}

    return app
