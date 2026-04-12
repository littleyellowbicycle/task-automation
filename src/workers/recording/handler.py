from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ...feishu_recorder.client import FeishuClient
from ...feishu_recorder.models import TaskRecord, TaskStatus
from ...utils import get_logger

logger = get_logger("workers.recording.handler")


class RecordingHandler:
    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        feishu_app_id: str = "",
        feishu_app_secret: str = "",
        feishu_table_id: str = "",
        feishu_webhook_url: str = "",
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.feishu_client = FeishuClient(
            app_id=feishu_app_id,
            app_secret=feishu_app_secret,
            table_id=feishu_table_id,
        )
        self.feishu_webhook_url = feishu_webhook_url

    async def handle_recording_request(
        self,
        task_id: str,
        task_record: Dict[str, Any],
        success: bool,
        message: str = "",
    ) -> Dict[str, Any]:
        status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

        record = TaskRecord(
            task_id=task_id,
            raw_message=task_record.get("raw_message", ""),
            summary=task_record.get("summary", ""),
            status=status,
            user_id=task_record.get("user_id"),
            user_name=task_record.get("user_name"),
            code_repo_url=task_record.get("repo_url"),
            executor_result=message,
        )

        feishu_success = False
        try:
            feishu_success = self.feishu_client.create_record(record)
            logger.info(f"Recorded task {task_id} to Feishu: {feishu_success}")
        except Exception as e:
            logger.error(f"Failed to record to Feishu: {e}")

        recording_data = {
            "task_id": task_id,
            "success": success,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.gateway_url}/api/v1/recording/done",
                    json=recording_data,
                )
        except Exception as e:
            logger.error(f"Failed to callback gateway: {e}")

        return {"code": 0, "action": "recorded"}
