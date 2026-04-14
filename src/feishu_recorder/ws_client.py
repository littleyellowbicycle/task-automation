from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Awaitable, Callable, Dict, Optional

import lark_oapi as lark
from lark_oapi.ws import Client as WSClient

from ..utils import get_logger

logger = get_logger("feishu_ws_client")


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
        builder = builder.register_p2_card_action_trigger_v1(
            self._handle_card_action_v2
        )
        builder = builder.register_p1_customized_event(
            "card.action.trigger",
            self._handle_card_action_v1
        )
        return builder.build()

    def _handle_card_action_v2(self, data: lark.card.v1.P2CardActionTriggerV1) -> None:
        try:
            logger.info(f"Received card action v2: {lark.JSON.marshal(data, indent=4)}")

            action = data.event.action
            if action and action.value:
                value = action.value
                task_id = value.get("task_id")
                action_type = value.get("action")

                logger.info(f"Card action: task_id={task_id}, action={action_type}")

                for handler in self._card_handlers:
                    try:
                        result = {
                            "task_id": task_id,
                            "action": action_type,
                            "raw_data": data,
                        }
                        if asyncio.iscoroutinefunction(handler):
                            asyncio.run(handler(result))
                        else:
                            handler(result)
                    except Exception as e:
                        logger.error(f"Card handler error: {e}")

        except Exception as e:
            logger.error(f"Error handling card action v2: {e}")

    def _handle_card_action_v1(self, data: lark.CustomizedEvent) -> None:
        try:
            logger.info(f"Received card action v1: {lark.JSON.marshal(data, indent=4)}")

            body = json.loads(data.body) if isinstance(data.body, str) else data.body

            action = body.get("action", {})
            value = action.get("value", {})
            task_id = value.get("task_id")
            action_type = value.get("action")

            logger.info(f"Card action v1: task_id={task_id}, action={action_type}")

            for handler in self._card_handlers:
                try:
                    result = {
                        "task_id": task_id,
                        "action": action_type,
                        "raw_data": body,
                    }
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.run(handler(result))
                    else:
                        handler(result)
                except Exception as e:
                    logger.error(f"Card handler error: {e}")

        except Exception as e:
            logger.error(f"Error handling card action v1: {e}")

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
        self._queue: asyncio.Queue = asyncio.Queue()

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
