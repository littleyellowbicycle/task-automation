from __future__ import annotations

from typing import Optional

from .models import TaskRecord, TaskStatus


class FeishuBridge:
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None, table_id: Optional[str] = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_id = table_id

    def write_record(self, record: TaskRecord) -> bool:
        # Placeholder bridge to Feishu API; returns True to indicate success
        return True
