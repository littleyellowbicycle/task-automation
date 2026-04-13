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
    api_url: str = "http://localhost:4096",
    work_dir: str = "./workspace",
    timeout: int = 600,
    model_provider: str = "opencode",
    model_id: str = "minimax-m2.5-free",
    opencode_host: str = "",
    opencode_port: int = 0,
) -> FastAPI:
    app = FastAPI(
        title="Execution Worker",
        version="2.0.0",
    )

    handler = ExecutionHandler(
        gateway_url=gateway_url,
        api_url=api_url,
        work_dir=work_dir,
        timeout=timeout,
        model_provider=model_provider,
        model_id=model_id,
        host=opencode_host,
        port=opencode_port,
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
