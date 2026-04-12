from __future__ import annotations

from fastapi import APIRouter, Request

from ...utils import get_logger

logger = get_logger("gateway.routes.queue")

router = APIRouter(prefix="/api/v1", tags=["queue"])


@router.get("/queue/status")
async def queue_status(request: Request):
    app = request.app
    queue_manager = app.state.queue_manager

    return {"code": 0, "data": queue_manager.stats}
