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
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_id = table_id
        self.webhook_url = webhook_url
        self.callback_url = callback_url
        self.client = FeishuClient(
            app_id, app_secret, table_id, 
            webhook_url=webhook_url,
            callback_url=callback_url
        )
    
    def set_callback_url(self, callback_url: str) -> None:
        """Set the callback URL for approval cards."""
        self.callback_url = callback_url
        self.client.callback_url = callback_url

    def write_record(self, record: TaskRecord) -> bool:
        """Write a task record to Feishu."""
        # If no credentials are provided, return True for testing purposes
        if not self.app_id or not self.app_secret or not self.table_id:
            logger.info("No Feishu credentials provided, skipping record creation (test mode)")
            return True
        return self.client.create_record(record)

    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status in Feishu."""
        return self.client.update_status(task_id, status.value)

    def send_approval_card(self, task_record: TaskRecord, callback_url: Optional[str] = None) -> bool:
        """Send task approval card."""
        card = self.client.create_task_card(task_record, callback_url)
        # For webhook, wrap in proper format
        webhook_card = {
            "msg_type": "interactive",
            "card": card
        }
        return self.client.send_webhook_card(webhook_card)

    def send_notification_card(self, task_record: TaskRecord, message: str) -> bool:
        """Send task notification card."""
        card = self.client.create_notification_card(task_record, message)
        # For webhook, wrap in proper format
        webhook_card = {
            "msg_type": "interactive",
            "card": card
        }
        return self.client.send_webhook_card(webhook_card)

    def handle_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Feishu card callback."""
        return self.client.handle_callback(callback_data)

    def health_check(self) -> bool:
        """Check if Feishu integration is healthy."""
        try:
            # Try to get token as a health check
            token = self.client._get_tenant_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Feishu health check failed: {e}")
            return False
