from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import httpx

from src.gateway.dispatcher.http_dispatcher import HttpDispatcher


class TestHttpDispatcher:
    def setup_method(self):
        self.dispatcher = HttpDispatcher(
            analysis_url="http://localhost:8001",
            decision_url="http://localhost:8002",
            execution_url="http://localhost:8003",
            recording_url="http://localhost:8004",
            timeout=5.0,
        )

    def test_init(self):
        assert self.dispatcher.analysis_url == "http://localhost:8001"
        assert self.dispatcher.decision_url == "http://localhost:8002"
        assert self.dispatcher.execution_url == "http://localhost:8003"
        assert self.dispatcher.recording_url == "http://localhost:8004"

    def test_init_strips_trailing_slash(self):
        d = HttpDispatcher(analysis_url="http://localhost:8001/")
        assert d.analysis_url == "http://localhost:8001"

    @pytest.mark.asyncio
    async def test_dispatch_to_analysis(self):
        with patch.object(self.dispatcher, "_post", return_value={"code": 0}) as mock_post:
            await self.dispatcher.dispatch_to_analysis("task_1", "test content", msg_id="m1")
            mock_post.assert_called_once()
            args = mock_post.call_args[0]
            assert "analyze" in args[0]
            assert args[1]["task_id"] == "task_1"
            assert args[1]["content"] == "test content"

    @pytest.mark.asyncio
    async def test_dispatch_to_decision(self):
        with patch.object(self.dispatcher, "_post", return_value={"code": 0}) as mock_post:
            await self.dispatcher.dispatch_to_decision("task_1", {"raw": "msg"}, {"summary": "test"})
            mock_post.assert_called_once()
            args = mock_post.call_args[0]
            assert "decision" in args[0]
            assert args[1]["task_id"] == "task_1"

    @pytest.mark.asyncio
    async def test_dispatch_to_decision_callback(self):
        with patch.object(self.dispatcher, "_post", return_value={"code": 0}) as mock_post:
            await self.dispatcher.dispatch_to_decision_callback("task_1", "approve")
            mock_post.assert_called_once()
            args = mock_post.call_args[0]
            assert "callback" in args[0]
            assert args[1]["task_id"] == "task_1"
            assert args[1]["action"] == "approve"

    @pytest.mark.asyncio
    async def test_dispatch_to_execution(self):
        with patch.object(self.dispatcher, "_post", return_value={"code": 0}) as mock_post:
            await self.dispatcher.dispatch_to_execution("task_1", "summary", raw_message="full")
            mock_post.assert_called_once()
            args = mock_post.call_args[0]
            assert "execution" in args[0]
            assert args[1]["task_id"] == "task_1"
            assert args[1]["summary"] == "summary"

    @pytest.mark.asyncio
    async def test_dispatch_to_recording(self):
        with patch.object(self.dispatcher, "_post", return_value={"code": 0}) as mock_post:
            await self.dispatcher.dispatch_to_recording("task_1", {"raw": "msg"}, True, "ok")
            mock_post.assert_called_once()
            args = mock_post.call_args[0]
            assert "recording" in args[0]
            assert args[1]["task_id"] == "task_1"
            assert args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_dispatch_timeout_raises(self):
        with patch.object(self.dispatcher, "_post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(httpx.TimeoutException):
                await self.dispatcher.dispatch_to_analysis("task_1", "content")

    @pytest.mark.asyncio
    async def test_dispatch_http_error_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        error = httpx.HTTPStatusError("error", request=MagicMock(), response=mock_resp)
        with patch.object(self.dispatcher, "_post", side_effect=error):
            with pytest.raises(httpx.HTTPStatusError):
                await self.dispatcher.dispatch_to_analysis("task_1", "content")

    @pytest.mark.asyncio
    async def test_dispatch_generic_error_raises(self):
        with patch.object(self.dispatcher, "_post", side_effect=ConnectionError("refused")):
            with pytest.raises(ConnectionError):
                await self.dispatcher.dispatch_to_analysis("task_1", "content")
