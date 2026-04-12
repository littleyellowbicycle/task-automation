from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .handler import RecordingHandler
from ...utils import get_logger

logger = get_logger("workers.recording.app")


class RecordingRequestModel(BaseModel):
    task_id: str
    task_record: Dict[str, Any] = Field(default_factory=dict)
    success: bool
    message: str = ""


def create_recording_app(
    gateway_url: str = "http://localhost:8000",
    port: int = 8004,
    feishu_app_id: str = "",
    feishu_app_secret: str = "",
    feishu_table_id: str = "",
    feishu_webhook_url: str = "",
) -> FastAPI:
    app = FastAPI(
        title="Recording Worker",
        version="2.0.0",
    )

    handler = RecordingHandler(
        gateway_url=gateway_url,
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        feishu_table_id=feishu_table_id,
        feishu_webhook_url=feishu_webhook_url,
    )

    @app.post("/worker/recording/request")
    async def recording_request(request: RecordingRequestModel):
        result = await handler.handle_recording_request(
            task_id=request.task_id,
            task_record=request.task_record,
            success=request.success,
            message=request.message,
        )
        return result

    @app.get("/health")
    async def health():
        return {"status": "healthy", "worker": "recording"}

    return app
