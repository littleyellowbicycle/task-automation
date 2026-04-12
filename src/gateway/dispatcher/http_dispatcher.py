from __future__ import annotations

from typing import Any, Dict

import httpx

from .base import Dispatcher
from ...utils import get_logger

logger = get_logger("gateway.http_dispatcher")


class HttpDispatcher(Dispatcher):
    def __init__(
        self,
        analysis_url: str = "http://localhost:8001",
        decision_url: str = "http://localhost:8002",
        execution_url: str = "http://localhost:8003",
        recording_url: str = "http://localhost:8004",
        timeout: float = 10.0,
    ):
        self.analysis_url = analysis_url.rstrip("/")
        self.decision_url = decision_url.rstrip("/")
        self.execution_url = execution_url.rstrip("/")
        self.recording_url = recording_url.rstrip("/")
        self.timeout = timeout

    async def dispatch_to_analysis(self, task_id: str, content: str, msg_id: str = "") -> None:
        payload = {"task_id": task_id, "content": content, "msg_id": msg_id}
        await self._post(f"{self.analysis_url}/worker/analyze", payload)

    async def dispatch_to_decision(self, task_id: str, task_record: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        payload = {"task_id": task_id, "task_record": task_record, "analysis": analysis}
        await self._post(f"{self.decision_url}/worker/decision/request", payload)

    async def dispatch_to_decision_callback(self, task_id: str, action: str) -> None:
        payload = {"task_id": task_id, "action": action}
        await self._post(f"{self.decision_url}/worker/decision/callback", payload)

    async def dispatch_to_execution(self, task_id: str, summary: str, raw_message: str = "") -> None:
        payload = {"task_id": task_id, "summary": summary, "raw_message": raw_message}
        await self._post(f"{self.execution_url}/worker/execution/request", payload)

    async def dispatch_to_recording(self, task_id: str, task_record: Dict[str, Any], success: bool, message: str = "") -> None:
        payload = {"task_id": task_id, "task_record": task_record, "success": success, "message": message}
        await self._post(f"{self.recording_url}/worker/recording/request", payload)

    async def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                logger.debug(f"Dispatched to {url}: {data.get('code', 'unknown')}")
                return data
        except httpx.TimeoutException:
            logger.error(f"Dispatch timeout: {url}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Dispatch failed: {url} - {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Dispatch error: {url} - {e}")
            raise
