from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.gateway.dispatcher.inprocess_dispatcher import InProcessDispatcher


class TestInProcessDispatcher:
    def setup_method(self):
        self.dispatcher = InProcessDispatcher()

    @pytest.mark.asyncio
    async def test_dispatch_to_analysis_no_handler(self):
        await self.dispatcher.dispatch_to_analysis("task_1", "content")

    @pytest.mark.asyncio
    async def test_dispatch_to_analysis_with_handler(self):
        handler = AsyncMock()
        self.dispatcher.set_analysis_handler(handler)
        await self.dispatcher.dispatch_to_analysis("task_1", "test content", msg_id="m1")
        handler.assert_called_once_with(task_id="task_1", content="test content", msg_id="m1")

    @pytest.mark.asyncio
    async def test_dispatch_to_decision_no_handler(self):
        await self.dispatcher.dispatch_to_decision("task_1", {}, {})

    @pytest.mark.asyncio
    async def test_dispatch_to_decision_with_handler(self):
        handler = AsyncMock()
        self.dispatcher.set_decision_handler(handler)
        await self.dispatcher.dispatch_to_decision("task_1", {"raw": "msg"}, {"summary": "test"})
        handler.assert_called_once_with(task_id="task_1", task_record={"raw": "msg"}, analysis={"summary": "test"})

    @pytest.mark.asyncio
    async def test_dispatch_to_decision_callback_no_handler(self):
        await self.dispatcher.dispatch_to_decision_callback("task_1", "approve")

    @pytest.mark.asyncio
    async def test_dispatch_to_decision_callback_with_handler(self):
        handler = AsyncMock()
        self.dispatcher.set_decision_callback_handler(handler)
        await self.dispatcher.dispatch_to_decision_callback("task_1", "approve")
        handler.assert_called_once_with(task_id="task_1", action="approve")

    @pytest.mark.asyncio
    async def test_dispatch_to_execution_no_handler(self):
        await self.dispatcher.dispatch_to_execution("task_1", "summary")

    @pytest.mark.asyncio
    async def test_dispatch_to_execution_with_handler(self):
        handler = AsyncMock()
        self.dispatcher.set_execution_handler(handler)
        await self.dispatcher.dispatch_to_execution("task_1", "do stuff", raw_message="full msg")
        handler.assert_called_once_with(task_id="task_1", summary="do stuff", raw_message="full msg")

    @pytest.mark.asyncio
    async def test_dispatch_to_recording_no_handler(self):
        await self.dispatcher.dispatch_to_recording("task_1", {}, True, "ok")

    @pytest.mark.asyncio
    async def test_dispatch_to_recording_with_handler(self):
        handler = AsyncMock()
        self.dispatcher.set_recording_handler(handler)
        await self.dispatcher.dispatch_to_recording("task_1", {"raw": "msg"}, False, "failed")
        handler.assert_called_once_with(task_id="task_1", task_record={"raw": "msg"}, success=False, message="failed")

    def test_set_all_handlers(self):
        self.dispatcher.set_analysis_handler(AsyncMock())
        self.dispatcher.set_decision_handler(AsyncMock())
        self.dispatcher.set_decision_callback_handler(AsyncMock())
        self.dispatcher.set_execution_handler(AsyncMock())
        self.dispatcher.set_recording_handler(AsyncMock())
        assert self.dispatcher._analysis_handler is not None
        assert self.dispatcher._decision_handler is not None
        assert self.dispatcher._decision_callback_handler is not None
        assert self.dispatcher._execution_handler is not None
        assert self.dispatcher._recording_handler is not None
