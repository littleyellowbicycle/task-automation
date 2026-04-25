from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Awaitable, Callable, Dict, Optional

import lark_oapi as lark
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)
from lark_oapi.ws import Client as WSClient
from lark_oapi.ws.client import MessageType

from ..utils import get_logger

logger = get_logger("feishu_ws_client")


def _patch_ws_client_card_handler() -> None:
    original_handle_data_frame = WSClient._handle_data_frame

    async def patched_handle_data_frame(self, frame):
        from lark_oapi.ws.client import (
            HEADER_MESSAGE_ID,
            HEADER_TRACE_ID,
            HEADER_SUM,
            HEADER_SEQ,
            HEADER_TYPE,
            HEADER_BIZ_RT,
            UTF_8,
            Frame,
            FrameType,
            Response,
            _get_by_key,
        )
        import base64
        import http
        import time
        from lark_oapi.core.model import JSON

        hs = frame.headers
        msg_id = _get_by_key(hs, HEADER_MESSAGE_ID)
        trace_id = _get_by_key(hs, HEADER_TRACE_ID)
        sum_ = _get_by_key(hs, HEADER_SUM)
        seq = _get_by_key(hs, HEADER_SEQ)
        type_ = _get_by_key(hs, HEADER_TYPE)

        pl = frame.payload
        if int(sum_) > 1:
            pl = self._combine(msg_id, int(sum_), int(seq), pl)
            if pl is None:
                return

        message_type = MessageType(type_)
        logger.debug(
            f"[WSClient] receive message, message_type: {message_type.value}, "
            f"message_id: {msg_id}, trace_id: {trace_id}"
        )

        resp = Response(code=http.HTTPStatus.OK)
        try:
            start = int(round(time.time() * 1000))
            if message_type == MessageType.EVENT:
                result = self._event_handler.do_without_validation(pl)
            elif message_type == MessageType.CARD:
                result = self._event_handler.do_without_validation(pl)
            else:
                return
            end = int(round(time.time() * 1000))
            header = hs.add()
            header.key = HEADER_BIZ_RT
            header.value = str(end - start)
            if result is not None:
                resp.data = base64.b64encode(JSON.marshal(result).encode(UTF_8))
        except Exception as e:
            logger.error(
                f"[WSClient] handle message failed, message_type: {message_type.value}, "
                f"message_id: {msg_id}, trace_id: {trace_id}, err: {e}"
            )
            resp = Response(code=http.HTTPStatus.INTERNAL_SERVER_ERROR)

        frame.payload = JSON.marshal(resp).encode(UTF_8)
        await self._write_message(frame.SerializeToString())

    WSClient._handle_data_frame = patched_handle_data_frame


_patch_ws_client_card_handler()


class FeishuWSClient:

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        log_level: lark.LogLevel = lark.LogLevel.INFO,
    ):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.log_level = log_level

        self._client: Optional[WSClient] = None
        self._event_handler: Optional[lark.EventDispatcherHandler] = None
        self._card_handlers: list[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

        if not self.app_id or not self.app_secret:
            logger.warning("FEISHU_APP_ID or FEISHU_APP_SECRET not configured")

    def _build_event_handler(self) -> lark.EventDispatcherHandler:
        builder = lark.EventDispatcherHandler.builder("", "")
        builder = builder.register_p2_card_action_trigger(
            self._handle_card_action_p2
        )
        return builder.build()

    def _handle_card_action_p2(self, data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
        try:
            logger.info("Received card action via WebSocket (P2)")

            event = data.event
            if not event or not event.action or not event.action.value:
                logger.warning("Card action event missing action value")
                return P2CardActionTriggerResponse()

            value = event.action.value
            task_id = value.get("task_id", "")
            action_type = value.get("action", "")

            logger.info(f"Card action: task_id={task_id}, action={action_type}")

            for handler in self._card_handlers:
                try:
                    result = {
                        "task_id": task_id,
                        "action": action_type,
                    }
                    if asyncio.iscoroutinefunction(handler):
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(handler(result))
                        except RuntimeError:
                            asyncio.run(handler(result))
                    else:
                        handler(result)
                except Exception as e:
                    logger.error(f"Card handler error: {e}")

        except Exception as e:
            logger.error(f"Error handling card action: {e}")

        return P2CardActionTriggerResponse()

    def on_card_action(
        self,
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> FeishuWSClient:
        self._card_handlers.append(handler)
        return self

    def start(self, blocking: bool = True) -> None:
        if not self.app_id or not self.app_secret:
            raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET must be configured")

        if self._running:
            logger.warning("WebSocket client is already running")
            return

        self._event_handler = self._build_event_handler()

        self._client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=self._event_handler,
            log_level=self.log_level,
        )

        self._running = True

        if blocking:
            logger.info("Starting Feishu WebSocket client (blocking mode)")
            self._run_client()
        else:
            logger.info("Starting Feishu WebSocket client (background thread)")
            self._thread = threading.Thread(target=self._run_client, daemon=True)
            self._thread.start()

    def _run_client(self) -> None:
        try:
            self._client.start()
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
            self._running = False

    def stop(self) -> None:
        self._running = False
        logger.info("WebSocket client stopped")

    def is_connected(self) -> bool:
        return self._running and self._client is not None


class FeishuWSClientAsync:

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        log_level: lark.LogLevel = lark.LogLevel.INFO,
    ):
        self._sync_client = FeishuWSClient(
            app_id=app_id,
            app_secret=app_secret,
            log_level=log_level,
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def on_card_action(
        self,
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> FeishuWSClientAsync:
        self._sync_client.on_card_action(handler)
        return self

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._sync_client.start(blocking=True),
        )

    async def start_background(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._sync_client.start(blocking=False)

    def stop(self) -> None:
        self._sync_client.stop()

    def is_connected(self) -> bool:
        return self._sync_client.is_connected()
