from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.requests import ExecutionDoneRequest, ExecutionProgressRequest
from ..models.tasks import TaskStatus
from ...utils import get_logger

logger = get_logger("gateway.routes.execution")

router = APIRouter(prefix="/api/v1", tags=["execution"])


@router.post("/execution/done")
async def execution_done(request: ExecutionDoneRequest, http_request: Request):
    app = http_request.app
    message_router = app.state.message_router
    task_manager = app.state.task_manager

    task = task_manager.get_task(request.task_id)
    if not task:
        return {"code": 404, "message": f"Task not found: {request.task_id}"}

    execution_data = {
        "success": request.success,
        "stdout": request.stdout,
        "stderr": request.stderr,
        "repo_url": request.repo_url,
        "files_created": request.files_created,
        "files_modified": request.files_modified,
        "duration": request.duration,
        "error_message": request.error_message,
    }

    try:
        await message_router.route_execution_done(request.task_id, execution_data)
    except Exception as e:
        logger.error(f"Failed to route execution result: {e}")
        return {"code": 500, "message": str(e)}

    return {"code": 0, "message": "execution_received", "task_id": request.task_id}


@router.post("/execution/progress")
async def execution_progress(request: ExecutionProgressRequest, http_request: Request):
    app = http_request.app
    task_manager = app.state.task_manager

    task = task_manager.get_task(request.task_id)
    if not task:
        return {"code": 404, "message": f"Task not found: {request.task_id}"}

    task.metadata["progress"] = request.progress
    task.metadata["current_step"] = request.current_step
    task.metadata["steps"] = request.steps

    logger.info(f"Task {request.task_id} progress: {request.progress}% - {request.current_step}")

    return {"code": 0, "message": "progress_updated", "task_id": request.task_id}
