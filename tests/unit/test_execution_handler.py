from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import httpx

from src.workers.execution.handler import ExecutionHandler
from src.code_executor import ExecutionResult


class TestExecutionHandler:
    def setup_method(self):
        self.handler = ExecutionHandler(
            gateway_url="http://localhost:8000",
            host="localhost",
            port=18792,
            work_dir="/tmp/test",
            timeout=60,
        )

    @pytest.mark.asyncio
    async def test_handle_execution_request_success(self):
        mock_result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="code generated",
            stderr="",
            duration=10.5,
            repo_url="https://github.com/test/repo",
        )
        with patch.object(self.handler.executor, "execute", return_value=mock_result):
            with patch("src.workers.execution.handler.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
                mock_cls.return_value = mock_client

                result = await self.handler.handle_execution_request(
                    task_id="task_1",
                    summary="login feature",
                    raw_message="develop a login feature",
                )
                assert result["code"] == 0
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handle_execution_request_failure(self):
        with patch.object(self.handler.executor, "execute", side_effect=Exception("execution error")):
            with patch("src.workers.execution.handler.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
                mock_cls.return_value = mock_client

                result = await self.handler.handle_execution_request(
                    task_id="task_2",
                    summary="fail task",
                )
                assert result["code"] == 0
                assert result["action"] == "execution_failed"

    @pytest.mark.asyncio
    async def test_handle_execution_request_gateway_unreachable(self):
        mock_result = ExecutionResult(success=True, exit_code=0, stdout="ok", stderr="", duration=1.0)
        with patch.object(self.handler.executor, "execute", return_value=mock_result):
            with patch("src.workers.execution.handler.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
                mock_cls.return_value = mock_client

                result = await self.handler.handle_execution_request(
                    task_id="task_3",
                    summary="test",
                )
                assert result["code"] == 0
