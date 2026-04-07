from __future__ import annotations

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import requests

from .models import TaskRecord, TaskStatus
from ..utils import get_logger

logger = get_logger("feishu_client")


class FeishuClient:
    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        table_id: Optional[str] = None,
        bitable_token: Optional[str] = None,
        base_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        callback_url: Optional[str] = None,
    ):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.table_id = table_id or os.getenv("FEISHU_TABLE_ID")
        self.bitable_token = bitable_token or os.getenv("FEISHU_BITABLE_TOKEN")
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL")
        self.callback_url = callback_url or os.getenv("FEISHU_CALLBACK_URL", "https://example.com")
        self.base_url = base_url or "https://open.feishu.cn/open-apis"
        self._tenant_access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _get_tenant_access_token(self) -> Optional[str]:
        if self._tenant_access_token and datetime.now().timestamp() < self._token_expires_at - 60:
            return self._tenant_access_token

        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self._tenant_access_token = data["tenant_access_token"]
                self._token_expires_at = datetime.now().timestamp() + data.get("expire", 7200)
                logger.info("Feishu tenant_access_token obtained")
                return self._tenant_access_token
            else:
                logger.error(f"Failed to get token: {data}")
                return None
        except Exception as e:
            logger.error(f"Feishu auth error: {e}")
            return None

    def _get_records(self, filter_formula: Optional[str] = None, page_size: int = 20) -> List[Dict[str, Any]]:
        token = self._get_tenant_access_token()
        if not token:
            return []

        url = f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.table_id}/records"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"page_size": page_size}
        if filter_formula:
            params["filter"] = filter_formula

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("items", [])
            logger.error(f"Failed to get records: {data}")
            return []
        except Exception as e:
            logger.error(f"Feishu get records error: {e}")
            return []

    def _find_record_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        formula = f'CurrentValue.[任务 ID]="{task_id}"'
        records = self._get_records(filter_formula=formula, page_size=1)
        return records[0] if records else None

    def create_record(self, record: TaskRecord) -> bool:
        token = self._get_tenant_access_token()
        if not token:
            logger.warning("No token, skipping Feishu record creation")
            return False

        if not self.bitable_token:
            logger.warning("No bitable_token configured for bitable")
            return False

        url = f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.table_id}/records"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        fields = {
            "任务 ID": record.task_id,
            "任务标题": record.summary,
            "任务描述": record.raw_message,
        }

        if record.tech_stack:
            fields["任务描述"] += f"\n\n技术栈: {', '.join(record.tech_stack)}"
        if record.core_features:
            fields["任务描述"] += f"\n核心功能: {', '.join(record.core_features)}"

        if record.status == TaskStatus.COMPLETED:
            fields["任务完成状态"] = True
        elif record.status == TaskStatus.PENDING:
            fields["任务完成状态"] = False

        if record.created_at:
            fields["创建时间"] = int(record.created_at.timestamp() * 1000)

        logger.debug(f"Creating record with fields: {fields}")

        try:
            payload = {"fields": fields}
            logger.debug(f"Sending payload: {payload}")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            logger.debug(f"Response: {data}")
            if data.get("code") == 0:
                logger.info(f"Created Feishu record for task {record.task_id}")
                return True
            else:
                logger.error(f"Failed to create record: {data}")
                return False
        except Exception as e:
            logger.error(f"Feishu create record error: {e}")
            return False

    def update_status(self, task_id: str, new_status: str) -> bool:
        record = self._find_record_by_task_id(task_id)
        if not record:
            logger.warning(f"Task {task_id} not found in Feishu")
            return False

        token = self._get_tenant_access_token()
        if not token:
            return False

        record_id = record.get("record_id")
        url = f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.table_id}/records/{record_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        fields = {
            "任务完成状态": new_status == "completed",
            "更新时间": int(datetime.now().timestamp() * 1000),
        }

        try:
            resp = requests.put(url, json={"fields": fields}, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                logger.info(f"Updated status for task {task_id} to {new_status}")
                return True
            else:
                logger.error(f"Failed to update record: {data}")
                return False
        except Exception as e:
            logger.error(f"Feishu update record error: {e}")
            return False

    def delete_record(self, task_id: str) -> bool:
        """
        Delete a record by task_id.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if deleted, False if not found or error
        """
        record = self._find_record_by_task_id(task_id)
        if not record:
            logger.warning(f"Task {task_id} not found in Feishu for deletion")
            return False

        token = self._get_tenant_access_token()
        if not token:
            return False

        record_id = record.get("record_id")
        url = f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.table_id}/records/{record_id}"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        try:
            resp = requests.delete(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                logger.info(f"Deleted Feishu record for task {task_id}")
                return True
            else:
                logger.error(f"Failed to delete record: {data}")
                return False
        except Exception as e:
            logger.error(f"Feishu delete record error: {e}")
            return False

    def delete_record_by_id(self, record_id: str) -> bool:
        """
        Delete a record by record_id directly.
        
        Args:
            record_id: Feishu record identifier
            
        Returns:
            True if deleted, False if error
        """
        token = self._get_tenant_access_token()
        if not token:
            return False

        url = f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.table_id}/records/{record_id}"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        try:
            resp = requests.delete(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                logger.info(f"Deleted Feishu record {record_id}")
                return True
            else:
                logger.error(f"Failed to delete record: {data}")
                return False
        except Exception as e:
            logger.error(f"Feishu delete record error: {e}")
            return False

    def send_private_message(
        self,
        user_id: str,
        content: Dict[str, Any],
        msg_type: str = "interactive",
    ) -> Optional[str]:
        """Send a private message to a user."""
        token = self._get_tenant_access_token()
        if not token:
            logger.warning("No token, skipping private message")
            return None

        url = f"{self.base_url}/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        params = {"receive_id_type": "user_id"}
        payload = {
            "receive_id": user_id,
            "msg_type": msg_type,
            "content": content if isinstance(content, str) else __import__("json").dumps(content),
        }

        try:
            resp = requests.post(url, params=params, json=payload, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                message_id = data.get("data", {}).get("message_id")
                logger.info(f"Private message sent to {user_id}: {message_id}")
                return message_id
            else:
                logger.error(f"Failed to send private message: {data}")
                return None
        except Exception as e:
            logger.error(f"Feishu private message error: {e}")
            return None

    def send_webhook_card(self, card_data: Dict[str, Any]) -> bool:
        """Send a Feishu card via webhook."""
        if not self.webhook_url:
            logger.warning("No webhook URL, skipping Feishu webhook card sending")
            return False

        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }

        try:
            resp = requests.post(self.webhook_url, json=card_data, headers=headers, timeout=10)
            data = resp.json()
            if data.get("StatusCode") == 0 or data.get("code") == 0:
                logger.info("Feishu webhook card sent successfully")
                return True
            else:
                logger.error(f"Failed to send webhook card: {data}")
                return False
        except Exception as e:
            logger.error(f"Feishu webhook card send error: {e}")
            return False

    def create_task_card(self, task_record: TaskRecord, callback_url: Optional[str] = None) -> Dict[str, Any]:
        """Create a task approval card with interactive buttons."""
        card = {
            "type": "interactive",
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"任务审批: {task_record.task_id}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**任务摘要**\n{task_record.summary}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**原始消息**\n{task_record.raw_message[:200] if len(task_record.raw_message) > 200 else task_record.raw_message}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**技术栈**: {', '.join(task_record.tech_stack) if task_record.tech_stack else '未知'}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**核心功能**: {', '.join(task_record.core_features) if task_record.core_features else '未知'}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 确认"
                            },
                            "type": "primary",
                            "url": f"{self.callback_url}/decision?task_id={task_record.task_id}&action=approve"
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 取消"
                            },
                            "type": "danger",
                            "url": f"{self.callback_url}/decision?task_id={task_record.task_id}&action=reject"
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "⏸️ 稍后"
                            },
                            "type": "default",
                            "url": f"{self.callback_url}/decision?task_id={task_record.task_id}&action=later"
                        }
                    ]
                }
            ]
        }
        return card

    def create_notification_card(self, task_record: TaskRecord, message: str) -> Dict[str, Any]:
        """Create a notification card."""
        card = {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"任务通知: {task_record.task_id}"
                },
                "template": "green" if task_record.status == TaskStatus.COMPLETED else "orange"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**消息**: {message}"
                },
                {
                    "tag": "markdown",
                    "content": f"**任务摘要**: {task_record.summary}"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": f"**状态**: {task_record.status.value}"
                    }
                }
            ]
        }

        if task_record.code_repo_url:
            card["elements"].append({
                "tag": "a",
                "text": {
                    "tag": "plain_text",
                    "content": "查看代码仓库"
                },
                "href": task_record.code_repo_url
            })

        return card

    def handle_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Feishu card callback."""
        try:
            action = callback_data.get("action", {})
            value = action.get("value", {})
            task_id = value.get("task_id")
            action_type = value.get("action")

            if not task_id or not action_type:
                return {"code": 400, "message": "Invalid callback data"}

            logger.info(f"Received callback for task {task_id}: {action_type}")

            return {
                "code": 0,
                "data": {
                    "task_id": task_id,
                    "action": action_type
                },
                "message": "Callback processed"
            }
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            return {"code": 500, "message": "Internal error"}
