from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ...feishu_recorder.feishu_bridge import FeishuBridge
from ...feishu_recorder.models import TaskRecord, TaskStatus
from ...utils import get_logger

logger = get_logger("workers.decision.handler")


@dataclass
class PendingConfirmation:
    task_id: str
    created_at: float
    timeout: float = 10800.0
    confirmed: bool = False
    decision: Optional[str] = None


class DecisionHandler:
    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        feishu_app_id: str = "",
        feishu_app_secret: str = "",
        feishu_webhook_url: str = "",
        feishu_user_id: str = "",
        default_timeout: float = 10800.0,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.default_timeout = default_timeout
        self.feishu_bridge = FeishuBridge(
            app_id=feishu_app_id,
            app_secret=feishu_app_secret,
            webhook_url=feishu_webhook_url,
            callback_url=f"{gateway_url}/api/v1/feishu/callback",
            user_id=feishu_user_id,
        )
        self._pending: Dict[str, PendingConfirmation] = {}

    async def handle_decision_request(
        self,
        task_id: str,
        task_record: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = TaskRecord(
            task_id=task_id,
            raw_message=task_record.get("raw_message", ""),
            summary=analysis.get("summary", ""),
            tech_stack=analysis.get("tech_stack", []),
            core_features=analysis.get("core_features", []),
            status=TaskStatus.PENDING,
            user_id=task_record.get("user_id"),
            user_name=task_record.get("user_name"),
        )

        callback_url = f"{self.gateway_url}/api/v1/feishu/callback"
        self.feishu_bridge.send_approval_card(record, callback_url=callback_url)

        self._pending[task_id] = PendingConfirmation(
            task_id=task_id,
            created_at=time.time(),
            timeout=self.default_timeout,
        )

        asyncio.create_task(self._check_timeout(task_id))

        logger.info(f"Decision request sent for task {task_id}")
        return {"code": 0, "task_id": task_id}

    async def handle_decision_callback(
        self,
        task_id: str,
        action: str,
    ) -> Dict[str, Any]:
        pending = self._pending.get(task_id)
        if pending:
            pending.confirmed = True
            pending.decision = action

        logger.info(f"Decision callback: task={task_id}, action={action}")
        return {"code": 0, "task_id": task_id, "action": action}

    async def _check_timeout(self, task_id: str) -> None:
        pending = self._pending.get(task_id)
        if not pending:
            return

        await asyncio.sleep(pending.timeout)

        if task_id in self._pending and not self._pending[task_id].confirmed:
            logger.warning(f"Task {task_id} decision timed out")
            self._pending.pop(task_id, None)
