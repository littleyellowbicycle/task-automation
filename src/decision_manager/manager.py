from __future__ import annotations

import asyncio
from typing import Optional

from ..feishu_recorder.models import TaskRecord, TaskStatus


class DecisionManager:
    """Simple decision manager for task confirmations.

    This is a lightweight placeholder that provides:
    - format_confirmation(record): produce a human-readable confirmation message
    - wait_confirmation(task_id): asynchronous wait for user confirmation (simulated)
    """

    def __init__(self, timeout: int = 300) -> None:
        self.timeout = int(timeout)

    def format_confirmation(self, record: TaskRecord) -> str:
        summary = getattr(record, "summary", "")
        tech = getattr(record, "tech_stack", [])
        features = getattr(record, "core_features", [])
        return (
            f"## Task Confirmation\n"
            f"Summary: {summary}\n"
            f"Tech Stack: {', '.join(tech)}\n"
            f"Core Features: {', '.join(features)}\n"
            f"Execute Command: opencode <instruction>\n"
        )

    async def wait_confirmation(self, task_id: str) -> bool:
        await asyncio.sleep(min(self.timeout, 0.1))
        return False
