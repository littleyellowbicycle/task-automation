from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.workers.filter_analysis.handler import FilterAnalysisHandler


class TestFilterAnalysisHandler:
    def setup_method(self):
        self.handler = FilterAnalysisHandler()

    @pytest.mark.asyncio
    async def test_handle_analyze_task_message(self):
        with patch.object(self.handler.task_filter, "filter", return_value=(
            MagicMock(is_task=True, confidence=0.9, category="development"),
            MagicMock(is_duplicate=False),
        )):
            with patch.object(self.handler.task_analyzer, "analyze", return_value={
                "summary": "login feature",
                "tech_stack": ["Python", "Flask"],
                "core_features": ["auth"],
                "estimated_complexity": "simple",
            }):
                result = await self.handler.handle_analyze("task_1", "develop a login feature")
                assert result["is_task"] is True
                assert result["summary"] == "login feature"
                assert "Python" in result["tech_stack"]
                assert result["complexity"] == "simple"

    @pytest.mark.asyncio
    async def test_handle_analyze_non_task_message(self):
        with patch.object(self.handler.task_filter, "filter", return_value=(
            MagicMock(is_task=False, confidence=0.2, category=None),
            MagicMock(is_duplicate=False),
        )):
            result = await self.handler.handle_analyze("task_2", "hello how are you")
            assert result["is_task"] is False
            assert result["reason"] == "not_task"

    @pytest.mark.asyncio
    async def test_handle_analyze_duplicate_message(self):
        with patch.object(self.handler.task_filter, "filter", return_value=(
            MagicMock(is_task=True, confidence=0.9, category="development"),
            MagicMock(is_duplicate=True),
        )):
            result = await self.handler.handle_analyze("task_3", "develop a login feature", msg_id="dup_001")
            assert result["is_task"] is False
            assert result["reason"] == "duplicate"

    @pytest.mark.asyncio
    async def test_handle_analyze_task_no_analysis_detail(self):
        with patch.object(self.handler.task_filter, "filter", return_value=(
            MagicMock(is_task=True, confidence=0.8, category="bugfix"),
            MagicMock(is_duplicate=False),
        )):
            with patch.object(self.handler.task_analyzer, "analyze", return_value={
                "summary": "fix bug",
            }):
                result = await self.handler.handle_analyze("task_4", "fix a bug")
                assert result["is_task"] is True
                assert result["summary"] == "fix bug"
                assert result["tech_stack"] == []
                assert result["complexity"] == "simple"
