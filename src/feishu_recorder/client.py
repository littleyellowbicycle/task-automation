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
        base_url: Optional[str] = None,
    ):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.table_id = table_id or os.getenv("FEISHU_TABLE_ID")
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

        url = f"{self.base_url}/bitable/v1/databases/{self.table_id}/records"
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
        formula = f'filterByFormula={{"task_id":"{task_id}"}}'
        records = self._get_records(filter_formula=formula, page_size=1)
        return records[0] if records else None

    def create_record(self, record: TaskRecord) -> bool:
        token = self._get_tenant_access_token()
        if not token:
            logger.warning("No token, skipping Feishu record creation")
            return False

        url = f"{self.base_url}/bitable/v1/databases/{self.table_id}/records"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        fields = {
            "task_id": record.task_id,
            "raw_message": record.raw_message,
            "summary": record.summary,
            "tech_stack": ",".join(record.tech_stack) if record.tech_stack else "",
            "core_features": ",".join(record.core_features) if record.core_features else "",
            "status": record.status.value,
            "code_repo_url": record.code_repo_url or "",
        }

        if record.created_at:
            fields["created_at"] = int(record.created_at.timestamp())
        if record.updated_at:
            fields["updated_at"] = int(record.updated_at.timestamp())

        try:
            resp = requests.post(url, json={"fields": fields}, headers=headers, timeout=10)
            data = resp.json()
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
        url = f"{self.base_url}/bitable/v1/databases/{self.table_id}/records/{record_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        fields = {
            "status": new_status,
            "updated_at": int(datetime.now().timestamp()),
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
