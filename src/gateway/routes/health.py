from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from ...utils import get_logger

logger = get_logger("gateway.routes.health")

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    app = request.app
    task_manager = app.state.task_manager
    queue_manager = app.state.queue_manager
    message_processor = app.state.message_processor

    ws_client = getattr(app.state, "feishu_ws_client", None)
    feishu_use_websocket = getattr(app.state, "feishu_use_websocket", False)

    feishu_status = {
        "mode": "websocket" if feishu_use_websocket else "http_callback",
    }
    if feishu_use_websocket:
        feishu_status["ws_connected"] = ws_client.is_connected() if ws_client else False

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "queue": {
                "size": queue_manager.size,
                "max_size": queue_manager.config.max_size,
                "current_task": queue_manager.current_task,
            },
            "tasks": task_manager.stats.get("status_counts", {}),
            "message_processor": message_processor.stats,
            "feishu": feishu_status,
        },
    }
