from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.requests import DecisionRequest
from ..models.tasks import TaskStatus
from ...utils import get_logger

logger = get_logger("gateway.routes.decisions")

router = APIRouter(prefix="/api/v1", tags=["decisions"])


@router.post("/decisions")
async def receive_decision(request: DecisionRequest, http_request: Request):
    app = http_request.app
    message_router = app.state.message_router
    task_manager = app.state.task_manager

    task = task_manager.get_task(request.task_id)
    if not task:
        return {"code": 404, "message": f"Task not found: {request.task_id}"}

    valid_actions = {"approve", "reject", "later", "timeout"}
    if request.action not in valid_actions:
        return {"code": 400, "message": f"Invalid action: {request.action}. Must be one of: {valid_actions}"}

    try:
        await message_router.route_decision(request.task_id, request.action)
    except Exception as e:
        logger.error(f"Failed to route decision: {e}")
        return {"code": 500, "message": str(e)}

    return {"code": 0, "message": "decision_processed", "task_id": request.task_id, "action": request.action}
