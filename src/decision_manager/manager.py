from __future__ import annotations

import asyncio
import os
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..feishu_recorder.models import TaskRecord, TaskStatus
from ..utils import get_logger

logger = get_logger("decision_manager")


class Decision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class PendingConfirmation:
    task_id: str
    record: TaskRecord
    created_at: float
    confirmed: bool = False
    decision: Optional[Decision] = None


class DecisionManager:
    """Decision manager for task confirmations via WeChat private chat.

    Flow:
    1. format_confirmation() - produce human-readable message
    2. send_confirmation() - send to WeChat private chat via webhook/bot
    3. wait_confirmation() - poll for user response
    """

    def __init__(
        self,
        timeout: int = 300,
        poll_interval: int = 2,
        wechat_webhook_url: Optional[str] = None,
        wechat_user_id: Optional[str] = None,
    ) -> None:
        self.timeout = int(timeout)
        self.poll_interval = int(poll_interval)
        self.wechat_webhook_url = wechat_webhook_url or os.getenv("WECHAT_WEBHOOK_URL")
        self.wechat_user_id = wechat_user_id or os.getenv("WECHAT_USER_ID")
        self._pending: Dict[str, PendingConfirmation] = {}

    def format_confirmation(self, record: TaskRecord) -> str:
        summary = getattr(record, "summary", "")
        tech = getattr(record, "tech_stack", [])
        features = getattr(record, "core_features", [])
        return (
            f"## 任务确认\n"
            f"📋 摘要: {summary}\n"
            f"🛠️ 技术栈: {', '.join(tech) if tech else '未识别'}\n"
            f"⚡ 功能点: {', '.join(features) if features else '基础功能'}\n\n"
            f"回复「确认」执行 | 回复「取消」终止\n"
            f"⏱️ 超时 {self.timeout//60} 分钟自动取消"
        )

    def send_confirmation(self, record: TaskRecord) -> bool:
        if not self.wechat_webhook_url:
            logger.warning("No WeChat webhook URL configured, skipping send")
            return False

        import requests

        msg = self.format_confirmation(record)
        payload = {
            "msgtype": "text",
            "text": {"content": msg},
        }

        try:
            resp = requests.post(self.wechat_webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Confirmation sent for task {record.task_id}")
                return True
            else:
                logger.error(f"Failed to send confirmation: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending confirmation: {e}")
            return False

    async def wait_confirmation(self, task_id: str, record: TaskRecord) -> Decision:
        pending = PendingConfirmation(
            task_id=task_id,
            record=record,
            created_at=time.time(),
        )
        self._pending[task_id] = pending

        self.send_confirmation(record)

        start = time.time()
        while time.time() - start < self.timeout:
            await asyncio.sleep(self.poll_interval)

            if task_id in self._pending and self._pending[task_id].confirmed:
                decision = self._pending[task_id].decision
                del self._pending[task_id]
                logger.info(f"Task {task_id} decision: {decision}")
                return decision or Decision.TIMEOUT

        del self._pending[task_id]
        logger.warning(f"Task {task_id} confirmation timed out")
        return Decision.TIMEOUT

    def receive_decision(self, task_id: str, message: str) -> bool:
        if task_id not in self._pending:
            logger.warning(f"No pending confirmation for task {task_id}")
            return False

        msg_lower = message.lower().strip()
        if msg_lower in ["确认", "yes", "y", "execute", "ok", "同意"]:
            self._pending[task_id].confirmed = True
            self._pending[task_id].decision = Decision.APPROVED
            return True
        elif msg_lower in ["取消", "no", "n", "reject", "不同意"]:
            self._pending[task_id].confirmed = True
            self._pending[task_id].decision = Decision.REJECTED
            return True

        return False
