from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.requests import AnalysisDoneRequest
from ..models.tasks import TaskStatus
from ...utils import get_logger

logger = get_logger("gateway.routes.analysis")

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analysis/done")
async def analysis_done(request: AnalysisDoneRequest, http_request: Request):
    app = http_request.app
    message_router = app.state.message_router
    task_manager = app.state.task_manager

    task = task_manager.get_task(request.task_id)
    if not task:
        return {"code": 404, "message": f"Task not found: {request.task_id}"}

    analysis_data = {
        "is_task": request.is_task,
        "summary": request.summary,
        "tech_stack": request.tech_stack,
        "core_features": request.core_features,
        "complexity": request.complexity,
        "category": request.category,
        "reason": request.reason,
    }

    try:
        await message_router.route_analysis_done(request.task_id, analysis_data)
    except Exception as e:
        logger.error(f"Failed to route analysis result: {e}")
        return {"code": 500, "message": str(e)}

    return {"code": 0, "message": "analysis_received", "task_id": request.task_id}
