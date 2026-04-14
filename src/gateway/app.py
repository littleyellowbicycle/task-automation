from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI

from .core import MessageProcessor, TaskManager, MessageRouter, QueueManager
from .core.queue_manager import QueueConfig
from .core.message_processor import DeduplicationConfig
from .dispatcher import Dispatcher, HttpDispatcher, InProcessDispatcher
from .routes import (
    listener_router,
    feishu_callback_router,
    decisions_router,
    analysis_router,
    execution_router,
    recording_router,
    tasks_router,
    queue_router,
    health_router,
)
from ..utils import get_logger

logger = get_logger("gateway.app")


def create_gateway_app(
    mode: str = "distributed",
    dedup_enabled: bool = True,
    dedup_max_cache: int = 1000,
    dedup_ttl: int = 3600,
    queue_max_size: int = 20,
    queue_confirmation_timeout: int = 10800,
    analysis_url: str = "http://localhost:8001",
    decision_url: str = "http://localhost:8002",
    execution_url: str = "http://localhost:8003",
    recording_url: str = "http://localhost:8004",
    dispatcher: Optional[Dispatcher] = None,
    feishu_use_websocket: bool = False,
    feishu_app_id: str = "",
    feishu_app_secret: str = "",
) -> FastAPI:
    app = FastAPI(
        title="WeChat Task Automation - API Gateway",
        description="Gateway service for message routing and task management",
        version="2.0.0",
    )

    message_processor = MessageProcessor(
        dedup_config=DeduplicationConfig(
            enabled=dedup_enabled,
            max_cache_size=dedup_max_cache,
            ttl_seconds=dedup_ttl,
        )
    )

    task_manager = TaskManager()

    queue_manager = QueueManager(
        config=QueueConfig(
            max_size=queue_max_size,
            confirmation_timeout=queue_confirmation_timeout,
        )
    )

    if dispatcher is not None:
        actual_dispatcher = dispatcher
    elif mode == "standalone":
        actual_dispatcher = InProcessDispatcher()
    else:
        actual_dispatcher = HttpDispatcher(
            analysis_url=analysis_url,
            decision_url=decision_url,
            execution_url=execution_url,
            recording_url=recording_url,
        )

    message_router = MessageRouter(
        task_manager=task_manager,
        queue_manager=queue_manager,
        dispatcher=actual_dispatcher,
    )

    app.state.message_processor = message_processor
    app.state.task_manager = task_manager
    app.state.queue_manager = queue_manager
    app.state.message_router = message_router
    app.state.dispatcher = actual_dispatcher
    app.state.mode = mode
    app.state.feishu_use_websocket = feishu_use_websocket
    app.state.feishu_ws_client = None

    app.include_router(listener_router)
    app.include_router(feishu_callback_router)
    app.include_router(decisions_router)
    app.include_router(analysis_router)
    app.include_router(execution_router)
    app.include_router(recording_router)
    app.include_router(tasks_router)
    app.include_router(queue_router)
    app.include_router(health_router)

    @app.on_event("startup")
    async def startup():
        logger.info(f"Gateway starting in {mode} mode")

        if feishu_use_websocket and feishu_app_id and feishu_app_secret:
            from ..feishu_recorder.ws_client import FeishuWSClient

            async def _on_card_action(data: Dict[str, Any]) -> Dict[str, Any]:
                task_id = data.get("task_id", "")
                action = data.get("action", "")

                if not task_id or not action:
                    logger.warning(f"Invalid WebSocket card action: {data}")
                    return {"code": 400, "message": "Invalid data"}

                logger.info(f"WebSocket card action received: task_id={task_id}, action={action}")

                try:
                    result = await message_router.route_feishu_callback({
                        "event": {
                            "type": "card.action.trigger",
                            "action": {
                                "value": {
                                    "task_id": task_id,
                                    "action": action,
                                },
                            },
                        },
                    })
                    return result
                except Exception as e:
                    logger.error(f"Failed to route WebSocket card action: {e}")
                    return {"code": 500, "message": str(e)}

            ws_client = FeishuWSClient(
                app_id=feishu_app_id,
                app_secret=feishu_app_secret,
            )
            ws_client.on_card_action(_on_card_action)
            ws_client.start(blocking=False)
            app.state.feishu_ws_client = ws_client

            logger.info("Feishu WebSocket client started in background (gateway-managed)")

    @app.on_event("shutdown")
    async def shutdown():
        ws_client = getattr(app.state, "feishu_ws_client", None)
        if ws_client:
            logger.info("Stopping Feishu WebSocket client...")
            ws_client.stop()
            app.state.feishu_ws_client = None
            logger.info("Feishu WebSocket client stopped")

    return app
