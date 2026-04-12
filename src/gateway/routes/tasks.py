from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

from ..models.tasks import TaskStatus
from ...utils import get_logger

logger = get_logger("gateway.routes.tasks")

router = APIRouter(prefix="/api/v1", tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    app = request.app
    task_manager = app.state.task_manager

    task = task_manager.get_task(task_id)
    if not task:
        return {"code": 404, "message": f"Task not found: {task_id}"}

    return {"code": 0, "data": task.to_dict()}


@router.get("/tasks")
async def list_tasks(
    request: Request,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    app = request.app
    task_manager = app.state.task_manager

    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            return {"code": 400, "message": f"Invalid status: {status}"}

    result = task_manager.list_tasks(status=task_status, page=page, page_size=page_size)
    return {"code": 0, "data": result}
