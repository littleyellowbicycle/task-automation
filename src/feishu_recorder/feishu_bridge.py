from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from .models import TaskRecord, TaskStatus
from .client import FeishuClient
from .ws_client import FeishuWSClient
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
        use_websocket: bool = False,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_id = table_id
        self.webhook_url = webhook_url
        self.callback_url = callback_url
        self.user_id = user_id
        self.use_websocket = use_websocket

        self.client = FeishuClient(
            app_id, app_secret, table_id,
            webhook_url=webhook_url,
            callback_url=callback_url,
        )

        self._ws_client: Optional[FeishuWSClient] = None
        self._card_handlers: list[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = []

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
        effective_callback = callback_url if not self.use_websocket else None
        card = self.client.create_task_card(task_record, effective_callback)

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

    def on_card_action(
        self,
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> FeishuBridge:
        self._card_handlers.append(handler)

        if self._ws_client:
            self._ws_client.on_card_action(handler)

        return self

    def start_websocket(self, blocking: bool = False) -> None:
        if not self.use_websocket:
            logger.warning("WebSocket mode not enabled, use use_websocket=True")
            return

        if self._ws_client is not None:
            logger.warning("WebSocket client already running")
            return

        logger.info("Starting Feishu WebSocket long connection client...")

        self._ws_client = FeishuWSClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
        )

        for handler in self._card_handlers:
            self._ws_client.on_card_action(handler)

        self._ws_client.start(blocking=blocking)

        if not blocking:
            logger.info("WebSocket client started in background")

    def stop_websocket(self) -> None:
        if self._ws_client:
            self._ws_client.stop()
            self._ws_client = None
            logger.info("WebSocket client stopped")

    def is_websocket_connected(self) -> bool:
        return self._ws_client is not None and self._ws_client.is_connected()

    def get_callback_url(self) -> Optional[str]:
        if self.use_websocket:
            return None
        return self.callback_url
