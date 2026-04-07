from __future__ import annotations

import json
import asyncio
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..utils import get_logger

if TYPE_CHECKING:
    from ..queue import TaskQueue
    from ..feishu_recorder import FeishuClient

logger = get_logger("callback_server")


class Decision(str, Enum):
    APPROVED = "approve"
    REJECTED = "reject"
    LATER = "later"
    TIMEOUT = "timeout"


class DecisionRequest(BaseModel):
    task_id: str
    action: str


class CallbackServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        callback_path: str = "/feishu/callback",
        decision_path: str = "/decision",
    ):
        self.host = host
        self.port = port
        self.callback_path = callback_path
        self.decision_path = decision_path
        self.app = FastAPI(title="Task Automation Callback Server")
        self._decision_callback: Optional[Callable] = None
        self._pending_decisions: Dict[str, asyncio.Future] = {}
        self._task_queue: Optional["TaskQueue"] = None
        self._feishu_client: Optional["FeishuClient"] = None
        self._on_approved: Optional[Callable] = None
        self._on_rejected: Optional[Callable] = None
        self._on_later: Optional[Callable] = None
        self._setup_routes()

    def set_task_queue(self, queue: "TaskQueue") -> None:
        self._task_queue = queue

    def set_feishu_client(self, client: "FeishuClient") -> None:
        self._feishu_client = client

    def set_decision_callback(self, callback: Callable[[str, str], Any]) -> None:
        self._decision_callback = callback

    def on_approved(self, callback: Callable[[str], Any]) -> None:
        self._on_approved = callback

    def on_rejected(self, callback: Callable[[str], Any]) -> None:
        self._on_rejected = callback

    def on_later(self, callback: Callable[[str], Any]) -> None:
        self._on_later = callback

    async def _handle_decision(self, task_id: str, action: str) -> Dict[str, Any]:
        result = {
            "task_id": task_id,
            "action": action,
            "message": "",
            "queue_status": None,
        }
        
        if action == Decision.APPROVED.value:
            result["message"] = "任务已确认，开始执行"
            
            if self._task_queue:
                task = self._task_queue.get_task(task_id)
                if task:
                    task.metadata["decision"] = Decision.APPROVED.value
                    
                    if self._feishu_client:
                        from ..feishu_recorder.models import TaskRecord, TaskStatus
                        record = TaskRecord(
                            task_id=task_id,
                            raw_message=task.data.get("raw_message", ""),
                            summary=task.data.get("summary", ""),
                            tech_stack=task.data.get("tech_stack", []),
                            core_features=task.data.get("core_features", []),
                            status=TaskStatus.APPROVED,
                        )
                        self._feishu_client.create_record(record)
                        logger.info(f"Created Feishu record for approved task {task_id}")
            
            if self._on_approved:
                await self._invoke_callback(self._on_approved, task_id)
                    
        elif action == Decision.REJECTED.value:
            result["message"] = "任务已取消"
            if self._on_rejected:
                await self._invoke_callback(self._on_rejected, task_id)
            if self._task_queue:
                self._task_queue.cancel_task(task_id, reason="User rejected")
                
        elif action == Decision.LATER.value:
            result["message"] = "任务已放回队列，稍后处理"
            if self._on_later:
                await self._invoke_callback(self._on_later, task_id)
            if self._task_queue:
                self._task_queue.requeue_task(task_id, reason="User deferred")
                result["queue_status"] = {
                    "position": self._task_queue.get_pending_count(),
                    "requeue_count": self._task_queue.get_task(task_id).metadata.get("requeue_count", 1) if self._task_queue.get_task(task_id) else 0,
                }
        
        if self._decision_callback:
            await self._decision_callback(task_id, action)
        
        if task_id in self._pending_decisions:
            future = self._pending_decisions.pop(task_id)
            future.set_result(action)
        
        return result

    async def _invoke_callback(self, callback: Callable, *args) -> None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    def _setup_routes(self):
        @self.app.post(self.callback_path)
        async def feishu_callback(request: Request):
            body = await request.body()
            logger.info(f"Received Feishu callback: {body[:200]}")
            
            try:
                data = json.loads(body)
                
                if data.get("type") == "url_verification":
                    challenge = data.get("challenge", "")
                    logger.info(f"URL verification challenge: {challenge}")
                    return {"challenge": challenge}
                
                event = data.get("event", {})
                event_type = event.get("type")
                logger.info(f"Event type: {event_type}")
                
                if event_type == "card.action.trigger":
                    action = event.get("action", {})
                    value = action.get("value", {})
                    task_id = value.get("task_id")
                    action_type = value.get("action")
                    
                    if task_id and action_type:
                        logger.info(f"Card action: task={task_id}, action={action_type}")
                        result = await self._handle_decision(task_id, action_type)
                        return {"code": 0, "data": result}
                
                return {"code": 0}
                
            except Exception as e:
                logger.error(f"Callback error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get(self.decision_path)
        async def decision_get(task_id: str, action: str):
            logger.info(f"Decision via GET: task={task_id}, action={action}")
            
            if action not in [d.value for d in Decision]:
                raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {[d.value for d in Decision]}")
            
            result = await self._handle_decision(task_id, action)
            return {"code": 0, "data": result}

        @self.app.post(self.decision_path)
        async def decision_post(request: DecisionRequest):
            logger.info(f"Decision via POST: task={request.task_id}, action={request.action}")
            
            if request.action not in [d.value for d in Decision]:
                raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {[d.value for d in Decision]}")
            
            result = await self._handle_decision(request.task_id, request.action)
            return {"code": 0, "data": result}

        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "queue_size": self._task_queue.size if self._task_queue else 0,
                "pending_decisions": len(self._pending_decisions),
            }

        @self.app.get("/queue/status")
        async def queue_status():
            if not self._task_queue:
                return {"error": "No queue configured"}
            return self._task_queue.stats

    async def wait_for_decision(self, task_id: str, timeout: float = 10800) -> Optional[str]:
        if task_id in self._pending_decisions:
            return None
        
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_decisions[task_id] = future
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_decisions.pop(task_id, None)
            if self._task_queue:
                self._task_queue.timeout_task(task_id)
            return Decision.TIMEOUT.value

    def run(self):
        import uvicorn
        logger.info(f"Starting callback server on {self.host}:{self.port}")
        logger.info(f"Feishu callback URL: {self.callback_path}")
        logger.info(f"Decision URL: {self.decision_path}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
