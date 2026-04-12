from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.requests import RecordingDoneRequest
from ...utils import get_logger

logger = get_logger("gateway.routes.recording")

router = APIRouter(prefix="/api/v1", tags=["recording"])


@router.post("/recording/done")
async def recording_done(request: RecordingDoneRequest, http_request: Request):
    app = http_request.app
    message_router = app.state.message_router
    task_manager = app.state.task_manager

    task = task_manager.get_task(request.task_id)
    if not task:
        return {"code": 404, "message": f"Task not found: {request.task_id}"}

    recording_data = {
        "success": request.success,
        "record_id": request.record_id,
    }

    try:
        await message_router.route_recording_done(request.task_id, recording_data)
    except Exception as e:
        logger.error(f"Failed to route recording result: {e}")
        return {"code": 500, "message": str(e)}

    return {"code": 0, "message": "recording_received", "task_id": request.task_id}
