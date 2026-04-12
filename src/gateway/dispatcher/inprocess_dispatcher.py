from __future__ import annotations

from typing import Any, Dict, Optional

from .base import Dispatcher
from ...utils import get_logger

logger = get_logger("gateway.inprocess_dispatcher")


class InProcessDispatcher(Dispatcher):
    def __init__(self):
        self._analysis_handler = None
        self._decision_handler = None
        self._decision_callback_handler = None
        self._execution_handler = None
        self._recording_handler = None

    def set_analysis_handler(self, handler):
        self._analysis_handler = handler

    def set_decision_handler(self, handler):
        self._decision_handler = handler

    def set_decision_callback_handler(self, handler):
        self._decision_callback_handler = handler

    def set_execution_handler(self, handler):
        self._execution_handler = handler

    def set_recording_handler(self, handler):
        self._recording_handler = handler

    async def dispatch_to_analysis(self, task_id: str, content: str, msg_id: str = "") -> None:
        if self._analysis_handler:
            await self._analysis_handler(task_id=task_id, content=content, msg_id=msg_id)
        else:
            logger.warning("No analysis handler registered")

    async def dispatch_to_decision(self, task_id: str, task_record: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        if self._decision_handler:
            await self._decision_handler(task_id=task_id, task_record=task_record, analysis=analysis)
        else:
            logger.warning("No decision handler registered")

    async def dispatch_to_decision_callback(self, task_id: str, action: str) -> None:
        if self._decision_callback_handler:
            await self._decision_callback_handler(task_id=task_id, action=action)
        else:
            logger.warning("No decision callback handler registered")

    async def dispatch_to_execution(self, task_id: str, summary: str, raw_message: str = "") -> None:
        if self._execution_handler:
            await self._execution_handler(task_id=task_id, summary=summary, raw_message=raw_message)
        else:
            logger.warning("No execution handler registered")

    async def dispatch_to_recording(self, task_id: str, task_record: Dict[str, Any], success: bool, message: str = "") -> None:
        if self._recording_handler:
            await self._recording_handler(task_id=task_id, task_record=task_record, success=success, message=message)
        else:
            logger.warning("No recording handler registered")
