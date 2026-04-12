from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class Dispatcher(ABC):
    @abstractmethod
    async def dispatch_to_analysis(self, task_id: str, content: str, msg_id: str = "") -> None:
        pass

    @abstractmethod
    async def dispatch_to_decision(self, task_id: str, task_record: Dict[str, Any], analysis: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def dispatch_to_decision_callback(self, task_id: str, action: str) -> None:
        pass

    @abstractmethod
    async def dispatch_to_execution(self, task_id: str, summary: str, raw_message: str = "") -> None:
        pass

    @abstractmethod
    async def dispatch_to_recording(self, task_id: str, task_record: Dict[str, Any], success: bool, message: str = "") -> None:
        pass
