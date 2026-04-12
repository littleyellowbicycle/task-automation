from __future__ import annotations

from typing import Any, Dict

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .handler import FilterAnalysisHandler
from ...utils import get_logger

logger = get_logger("workers.filter_analysis.app")


class AnalyzeRequest(BaseModel):
    task_id: str
    content: str
    msg_id: str = ""


def create_filter_analysis_app(
    gateway_url: str = "http://localhost:8000",
    port: int = 8001,
) -> FastAPI:
    app = FastAPI(
        title="Filter & Analysis Worker",
        version="2.0.0",
    )

    handler = FilterAnalysisHandler()
    gateway_url = gateway_url.rstrip("/")

    @app.post("/worker/analyze")
    async def analyze_message(request: AnalyzeRequest):
        result = await handler.handle_analyze(
            task_id=request.task_id,
            content=request.content,
            msg_id=request.msg_id,
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{gateway_url}/api/v1/analysis/done",
                    json=result,
                )
        except Exception as e:
            logger.error(f"Failed to callback gateway: {e}")

        return {"code": 0, "action": "analyzed" if result.get("is_task") else "skipped"}

    @app.get("/health")
    async def health():
        return {"status": "healthy", "worker": "filter_analysis"}

    return app
