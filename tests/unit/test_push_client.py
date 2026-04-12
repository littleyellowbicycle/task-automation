from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import httpx

from src.listener_push import PushClient


def _make_ok_response(data=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = data or {"code": 0, "task_id": "task_1"}
    return resp


class TestPushClient:
    def setup_method(self):
        self.client = PushClient(
            gateway_url="http://localhost:8000",
            timeout=5.0,
            max_retries=2,
            retry_delay=0.01,
        )

    def test_init(self):
        assert self.client.gateway_url == "http://localhost:8000"
        assert self.client.max_retries == 2

    def test_init_strips_trailing_slash(self):
        client = PushClient(gateway_url="http://localhost:8000/")
        assert client.gateway_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_push_message_success(self):
        with patch("src.listener_push.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=_make_ok_response())
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await self.client.push_message(content="test message")
            assert result["code"] == 0
            assert result["task_id"] == "task_1"
            assert self.client.stats["total_pushed"] == 1

    @pytest.mark.asyncio
    async def test_push_message_with_all_fields(self):
        with patch("src.listener_push.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=_make_ok_response({"code": 0, "task_id": "task_2"}))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await self.client.push_message(
                content="develop login",
                sender_id="user_1",
                sender_name="Alice",
                conversation_id="group_1",
                conversation_type="group",
                msg_id="msg_001",
                platform="wework",
                listener_type="ntwork",
            )
            assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_push_message_timeout_retries(self):
        with patch("src.listener_push.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await self.client.push_message(content="timeout test")
            assert result["code"] == 500
            assert self.client.stats["total_failed"] == 1
            assert self.client.stats["total_retries"] == 2

    @pytest.mark.asyncio
    async def test_push_message_http_error_retries(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        error = httpx.HTTPStatusError("error", request=MagicMock(), response=mock_resp)

        with patch("src.listener_push.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=error)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await self.client.push_message(content="error test")
            assert result["code"] == 500

    @pytest.mark.asyncio
    async def test_push_message_retry_then_success(self):
        call_count = [0]

        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise httpx.TimeoutException("timeout")
            return _make_ok_response({"code": 0, "task_id": "task_3"})

        with patch("src.listener_push.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = side_effect
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await self.client.push_message(content="retry test")
            assert result["code"] == 0
            assert self.client.stats["total_pushed"] == 1
            assert self.client.stats["total_retries"] == 1

    def test_stats(self):
        stats = self.client.stats
        assert "total_pushed" in stats
        assert "total_failed" in stats
        assert "total_retries" in stats
