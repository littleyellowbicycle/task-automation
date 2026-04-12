from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ..utils import get_logger

logger = get_logger("listener.push_client")


class PushClient:
    def __init__(
        self,
        gateway_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._stats = {
            "total_pushed": 0,
            "total_failed": 0,
            "total_retries": 0,
        }

    async def push_message(
        self,
        content: str,
        sender_id: str = "unknown",
        sender_name: str = "unknown",
        conversation_id: str = "unknown",
        conversation_type: str = "private",
        msg_id: str = "",
        msg_type: str = "text",
        platform: str = "wework",
        listener_type: str = "unknown",
        timestamp: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "content": content,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "conversation_id": conversation_id,
            "conversation_type": conversation_type,
            "msg_id": msg_id,
            "msg_type": msg_type,
            "platform": platform,
            "listener_type": listener_type,
            "timestamp": timestamp,
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.gateway_url}/api/v1/listener/msg",
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    self._stats["total_pushed"] += 1
                    logger.info(f"Message pushed to gateway: {data.get('task_id', 'N/A')}")
                    return data
            except httpx.TimeoutException:
                self._stats["total_retries"] += 1
                last_error = "timeout"
                logger.warning(f"Push timeout (attempt {attempt + 1}/{self.max_retries})")
            except httpx.HTTPStatusError as e:
                self._stats["total_retries"] += 1
                last_error = f"HTTP {e.response.status_code}"
                logger.warning(f"Push failed (attempt {attempt + 1}/{self.max_retries}): {e.response.status_code}")
            except Exception as e:
                self._stats["total_retries"] += 1
                last_error = str(e)
                logger.warning(f"Push error (attempt {attempt + 1}/{self.max_retries}): {e}")

            if attempt < self.max_retries - 1:
                import asyncio
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        self._stats["total_failed"] += 1
        logger.error(f"Failed to push message after {self.max_retries} attempts: {last_error}")
        return {"code": 500, "message": f"Push failed: {last_error}"}

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)
