from __future__ import annotations

from typing import Optional, Dict, Any

from .models import TaskRecord, TaskStatus
from .client import FeishuClient
from ..utils import get_logger

logger = get_logger("feishu_bridge")


class FeishuBridge:
    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        table_id: Optional[str] = None,
        webhook_url: Optional[str] = None,
        callback_url: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_id = table_id
        self.webhook_url = webhook_url
        self.callback_url = callback_url
        self.user_id = user_id
        self.client = FeishuClient(
            app_id, app_secret, table_id,
            webhook_url=webhook_url,
            callback_url=callback_url,
        )

    def set_callback_url(self, callback_url: str) -> None:
        self.callback_url = callback_url
        self.client.callback_url = callback_url

    def write_record(self, record: TaskRecord) -> bool:
        if not self.app_id or not self.app_secret or not self.table_id:
            logger.info("No Feishu credentials provided, skipping record creation (test mode)")
            return True
        return self.client.create_record(record)

    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        return self.client.update_status(task_id, status.value)

    def send_approval_card(self, task_record: TaskRecord, callback_url: Optional[str] = None) -> bool:
        card = self.client.create_task_card(task_record, callback_url)

        if self.user_id:
            message_id = self.client.send_private_message(
                user_id=self.user_id,
                content=card,
                msg_type="interactive",
            )
            if message_id:
                logger.info(f"Approval card sent via bot to user {self.user_id}")
                return True
            else:
                logger.warning("Failed to send card via bot, trying webhook fallback")
        elif self.webhook_url:
            logger.info("No user_id configured, using webhook to send card")
        else:
            logger.warning("No user_id or webhook_url configured, cannot send approval card")
            return False

        webhook_card = {
            "msg_type": "interactive",
            "card": card,
        }
        return self.client.send_webhook_card(webhook_card)

    def send_notification_card(self, task_record: TaskRecord, message: str) -> bool:
        card = self.client.create_notification_card(task_record, message)

        if self.user_id:
            message_id = self.client.send_private_message(
                user_id=self.user_id,
                content=card,
                msg_type="interactive",
            )
            if message_id:
                logger.info(f"Notification card sent via bot to user {self.user_id}")
                return True
            else:
                logger.warning("Failed to send notification via bot, trying webhook fallback")
        elif self.webhook_url:
            logger.info("No user_id configured, using webhook to send notification")
        else:
            logger.warning("No user_id or webhook_url configured, cannot send notification card")
            return False

        webhook_card = {
            "msg_type": "interactive",
            "card": card,
        }
        return self.client.send_webhook_card(webhook_card)

    def handle_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.handle_callback(callback_data)

    def health_check(self) -> bool:
        try:
            token = self.client._get_tenant_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Feishu health check failed: {e}")
            return False
