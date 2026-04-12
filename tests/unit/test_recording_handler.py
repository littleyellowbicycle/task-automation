from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.workers.recording.handler import RecordingHandler
from src.feishu_recorder.models import TaskStatus


class TestRecordingHandler:
    def setup_method(self):
        self.handler = RecordingHandler(
            gateway_url="http://localhost:8000",
            feishu_app_id="test_id",
            feishu_app_secret="test_secret",
            feishu_table_id="test_table",
            feishu_webhook_url="",
        )

    @pytest.mark.asyncio
    async def test_handle_recording_request_success(self):
        with patch.object(self.handler.feishu_client, "create_record", return_value=True):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await self.handler.handle_recording_request(
                    task_id="task_1",
                    task_record={"raw_message": "test", "summary": "test task"},
                    success=True,
                    message="task completed",
                )
                assert result["code"] == 0
                assert result["action"] == "recorded"

    @pytest.mark.asyncio
    async def test_handle_recording_request_feishu_failure_does_not_affect_status(self):
        with patch.object(self.handler.feishu_client, "create_record", return_value=False):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_response = MagicMock(status_code=200)
                mock_response.json.return_value = {"code": 0}
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await self.handler.handle_recording_request(
                    task_id="task_2",
                    task_record={"raw_message": "test"},
                    success=True,
                    message="task completed",
                )
                assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_handle_recording_request_feishu_exception(self):
        with patch.object(self.handler.feishu_client, "create_record", side_effect=Exception("feishu error")):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await self.handler.handle_recording_request(
                    task_id="task_3",
                    task_record={"raw_message": "test"},
                    success=False,
                    message="execution failed",
                )
                assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_handle_recording_request_gateway_unreachable(self):
        with patch.object(self.handler.feishu_client, "create_record", return_value=True):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await self.handler.handle_recording_request(
                    task_id="task_4",
                    task_record={"raw_message": "test"},
                    success=True,
                    message="ok",
                )
                assert result["code"] == 0
