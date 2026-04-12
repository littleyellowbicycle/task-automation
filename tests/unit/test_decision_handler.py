from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.workers.decision.handler import DecisionHandler


class TestDecisionHandler:
    def setup_method(self):
        self.handler = DecisionHandler(
            gateway_url="http://localhost:8000",
            feishu_app_id="test_id",
            feishu_app_secret="test_secret",
            feishu_webhook_url="",
            default_timeout=60,
        )

    @pytest.mark.asyncio
    async def test_handle_decision_request(self):
        with patch.object(self.handler.feishu_bridge, "send_approval_card", return_value=True):
            result = await self.handler.handle_decision_request(
                task_id="task_1",
                task_record={"raw_message": "develop login", "user_id": "u1"},
                analysis={"summary": "login feature", "tech_stack": ["Python"]},
            )
            assert result["code"] == 0
            assert result["task_id"] == "task_1"
            assert "task_1" in self.handler._pending

    @pytest.mark.asyncio
    async def test_handle_decision_callback(self):
        self.handler._pending["task_1"] = MagicMock(confirmed=False, decision=None)
        result = await self.handler.handle_decision_callback("task_1", "approve")
        assert result["code"] == 0
        assert result["action"] == "approve"
        assert self.handler._pending["task_1"].confirmed is True
        assert self.handler._pending["task_1"].decision == "approve"

    @pytest.mark.asyncio
    async def test_handle_decision_callback_unknown_task(self):
        result = await self.handler.handle_decision_callback("nonexistent", "approve")
        assert result["code"] == 0
        assert result["task_id"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_pending_confirmation_stored(self):
        with patch.object(self.handler.feishu_bridge, "send_approval_card", return_value=True):
            await self.handler.handle_decision_request(
                task_id="task_2",
                task_record={"raw_message": "test"},
                analysis={"summary": "test"},
            )
            pending = self.handler._pending.get("task_2")
            assert pending is not None
            assert pending.task_id == "task_2"
            assert pending.confirmed is False
