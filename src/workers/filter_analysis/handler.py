from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...filter import TaskFilter, FilterResult, DeduplicationResult
from ...task_analyzer.analyzer import TaskAnalyzer
from ...utils import get_logger

logger = get_logger("workers.filter_analysis.handler")


class FilterAnalysisHandler:
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-0.6B",
        device: str = "auto",
        task_threshold: float = 0.5,
        dedup_threshold: float = 0.85,
    ):
        self.task_filter = TaskFilter()
        self.task_analyzer = TaskAnalyzer()

    async def handle_analyze(
        self,
        task_id: str,
        content: str,
        msg_id: str = "",
    ) -> Dict[str, Any]:
        filter_result, dedup_result = self.task_filter.filter(content, msg_id)

        if dedup_result.is_duplicate:
            logger.info(f"Duplicate message: {msg_id}")
            return {
                "task_id": task_id,
                "is_task": False,
                "reason": "duplicate",
            }

        if not filter_result.is_task:
            logger.info(f"Not a task: {msg_id}, confidence: {filter_result.confidence}")
            return {
                "task_id": task_id,
                "is_task": False,
                "reason": "not_task",
                "category": filter_result.category,
            }

        analysis = self.task_analyzer.analyze(content)

        logger.info(f"Task analyzed: {task_id}, complexity: {analysis.get('estimated_complexity', 'simple')}")

        return {
            "task_id": task_id,
            "is_task": True,
            "summary": analysis.get("summary", ""),
            "tech_stack": analysis.get("tech_stack", []),
            "core_features": analysis.get("core_features", []),
            "complexity": analysis.get("estimated_complexity", "simple"),
            "category": filter_result.category,
        }
