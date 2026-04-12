from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.requests import ListenerMessageRequest
from ..core.message_processor import ValidationError
from ...utils import get_logger

logger = get_logger("gateway.routes.listener")

router = APIRouter(prefix="/api/v1", tags=["listener"])


@router.post("/listener/msg")
async def receive_listener_message(request: ListenerMessageRequest, http_request: Request):
    app = http_request.app
    message_processor = app.state.message_processor
    task_manager = app.state.task_manager
    message_router = app.state.message_router

    raw_message = request.model_dump()

    try:
        standard_message = message_processor.process(
            raw_message,
            platform=request.platform,
            listener_type=request.listener_type,
        )
    except ValidationError as e:
        logger.warning(f"Message validation failed: {e}")
        return {"code": 400, "message": str(e)}

    if standard_message is None:
        return {"code": 200, "message": "duplicate", "task_id": None}

    task = task_manager.create_task(
        raw_message=standard_message.content,
        standard_message=standard_message.to_dict(),
    )

    try:
        await message_router.route_new_message(task.task_id)
    except Exception as e:
        logger.error(f"Failed to route message: {e}")
        return {"code": 500, "message": str(e), "task_id": task.task_id}

    return {"code": 0, "message": "accepted", "task_id": task.task_id}
