from __future__ import annotations

from typing import Any, Dict

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .handler import DecisionHandler
from ...utils import get_logger

logger = get_logger("workers.decision.app")


class DecisionRequestModel(BaseModel):
    task_id: str
    task_record: Dict[str, Any] = Field(default_factory=dict)
    analysis: Dict[str, Any] = Field(default_factory=dict)


class DecisionCallbackModel(BaseModel):
    task_id: str
    action: str


def create_decision_app(
    gateway_url: str = "http://localhost:8000",
    port: int = 8002,
    feishu_app_id: str = "",
    feishu_app_secret: str = "",
    feishu_webhook_url: str = "",
    feishu_user_id: str = "",
) -> FastAPI:
    app = FastAPI(
        title="Decision Worker",
        version="2.0.0",
    )

    handler = DecisionHandler(
        gateway_url=gateway_url,
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        feishu_webhook_url=feishu_webhook_url,
        feishu_user_id=feishu_user_id,
    )

    @app.post("/worker/decision/request")
    async def decision_request(request: DecisionRequestModel):
        result = await handler.handle_decision_request(
            task_id=request.task_id,
            task_record=request.task_record,
            analysis=request.analysis,
        )
        return {"code": 0, "action": "decision_sent"}

    @app.post("/worker/decision/callback")
    async def decision_callback(request: DecisionCallbackModel):
        result = await handler.handle_decision_callback(
            task_id=request.task_id,
            action=request.action,
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{gateway_url.rstrip('/')}/api/v1/decisions",
                    json={"task_id": request.task_id, "action": request.action},
                )
        except Exception as e:
            logger.error(f"Failed to callback gateway: {e}")

        return {"code": 0, "action": "callback_processed"}

    @app.get("/health")
    async def health():
        return {"status": "healthy", "worker": "decision"}

    return app
