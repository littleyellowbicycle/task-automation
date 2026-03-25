from __future__ import annotations

from typing import Optional
from dataclasses import dataclass

from .models import TaskRecord


class FeishuClient:
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None, table_id: Optional[str] = None, base_url: Optional[str] = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_id = table_id
        self.base_url = base_url or "https://open.feishu.cn/open-apis/bitable/v1"

    def create_record(self, record: TaskRecord) -> bool:
        return True

    def update_status(self, task_id: str, new_status: str) -> bool:
        return True
