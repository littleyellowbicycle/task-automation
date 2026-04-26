"""Main entry point for WeChat Task Automation System v2."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.config.models import AppConfig
from src.utils import setup_logger, get_logger


def parse_args():
    parser = argparse.ArgumentParser(description="WeChat Task Automation System v2")
    parser.add_argument(
        "--mode",
        choices=["standalone", "gateway", "filter-analysis", "decision", "execution", "recording", "listener"],
        default="standalone",
        help="Run mode (default: standalone)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't actually execute code generation")
    parser.add_argument("--config", type=str, help="Path to config.yaml")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


def run_standalone(config: AppConfig, dry_run: bool = False):
    from src.gateway import create_gateway_app, InProcessDispatcher
    from src.gateway.core import TaskManager, QueueManager, MessageRouter, MessageProcessor
    from src.gateway.core.queue_manager import QueueConfig
    from src.gateway.core.message_processor import DeduplicationConfig

    from src.workers.filter_analysis.handler import FilterAnalysisHandler
    from src.workers.decision.handler import DecisionHandler
    from src.workers.execution.handler import ExecutionHandler
    from src.workers.recording.handler import RecordingHandler

    logger = get_logger("main.standalone")

    dispatcher = InProcessDispatcher()

    handler_analysis = FilterAnalysisHandler()
    handler_decision = DecisionHandler(
        gateway_url=f"http://localhost:{config.gateway.port}",
        feishu_app_id=config.feishu.app_id,
        feishu_app_secret=config.feishu.app_secret,
        feishu_webhook_url=config.feishu.webhook_url,
        feishu_user_id=config.feishu.user_id,
        feishu_use_websocket=config.feishu.use_websocket,
    )
    handler_execution = ExecutionHandler(
        gateway_url=f"http://localhost:{config.gateway.port}",
        api_url=config.opencode.api_url or "http://localhost:4096",
        work_dir=config.opencode.work_dir,
        timeout=config.opencode.timeout,
        model_provider=os.getenv("EXECUTOR_MODEL_PROVIDER", "opencode"),
        model_id=os.getenv("EXECUTOR_MODEL_ID", "minimax-m2.5-free"),
        host=config.opencode.host,
        port=config.opencode.port,
    )
    handler_recording = RecordingHandler(
        gateway_url=f"http://localhost:{config.gateway.port}",
        feishu_app_id=config.feishu.app_id,
        feishu_app_secret=config.feishu.app_secret,
        feishu_table_id=config.feishu.table_id,
        feishu_webhook_url=config.feishu.webhook_url,
    )

    async def _on_analysis(task_id: str, content: str, msg_id: str = ""):
        result = await handler_analysis.handle_analyze(task_id=task_id, content=content, msg_id=msg_id)
        from src.gateway.models.tasks import TaskStatus

        app = _get_app()
        tm = app.state.task_manager
        mr = app.state.message_router

        if not result.get("is_task"):
            tm.update_status(task_id, TaskStatus.CANCELLED, error=result.get("reason", "not_task"))
            return

        await mr.route_analysis_done(task_id, result)

    async def _on_decision(task_id: str, task_record: dict, analysis: dict):
        result = await handler_decision.handle_decision_request(
            task_id=task_id, task_record=task_record, analysis=analysis
        )

    async def _on_decision_callback(task_id: str, action: str):
        result = await handler_decision.handle_decision_callback(task_id=task_id, action=action)
        app = _get_app()
        mr = app.state.message_router
        await mr.route_decision(task_id, action)

    async def _on_execution(task_id: str, summary: str, raw_message: str = ""):
        result = await handler_execution.handle_execution_request(
            task_id=task_id, summary=summary, raw_message=raw_message
        )

    async def _on_recording(task_id: str, task_record: dict, success: bool, message: str = ""):
        result = await handler_recording.handle_recording_request(
            task_id=task_id, task_record=task_record, success=success, message=message
        )

    dispatcher.set_analysis_handler(_on_analysis)
    dispatcher.set_decision_handler(_on_decision)
    dispatcher.set_decision_callback_handler(_on_decision_callback)
    dispatcher.set_execution_handler(_on_execution)
    dispatcher.set_recording_handler(_on_recording)

    app = create_gateway_app(
        mode="standalone",
        dedup_enabled=config.gateway.dedup_enabled,
        dedup_max_cache=config.gateway.dedup_max_cache,
        dedup_ttl=config.gateway.dedup_ttl,
        queue_max_size=config.queue.max_size,
        queue_confirmation_timeout=config.queue.confirmation_timeout,
        dispatcher=dispatcher,
        feishu_use_websocket=config.feishu.use_websocket,
        feishu_app_id=config.feishu.app_id,
        feishu_app_secret=config.feishu.app_secret,
    )

    _app_ref = [app]

    def _get_app():
        return _app_ref[0]

    logger.info(f"Starting standalone gateway on {config.gateway.host}:{config.gateway.port}")
    uvicorn.run(app, host=config.gateway.host, port=config.gateway.port)


def run_gateway(config: AppConfig):
    from src.gateway import create_gateway_app

    logger = get_logger("main.gateway")

    app = create_gateway_app(
        mode="distributed",
        dedup_enabled=config.gateway.dedup_enabled,
        dedup_max_cache=config.gateway.dedup_max_cache,
        dedup_ttl=config.gateway.dedup_ttl,
        queue_max_size=config.queue.max_size,
        queue_confirmation_timeout=config.queue.confirmation_timeout,
        analysis_url=config.worker_urls.analysis_url,
        decision_url=config.worker_urls.decision_url,
        execution_url=config.worker_urls.execution_url,
        recording_url=config.worker_urls.recording_url,
        feishu_use_websocket=config.feishu.use_websocket,
        feishu_app_id=config.feishu.app_id,
        feishu_app_secret=config.feishu.app_secret,
    )

    logger.info(f"Starting gateway on {config.gateway.host}:{config.gateway.port}")
    uvicorn.run(app, host=config.gateway.host, port=config.gateway.port)


def run_filter_analysis_worker(config: AppConfig):
    from src.workers.filter_analysis import create_filter_analysis_app

    logger = get_logger("main.filter_analysis_worker")
    app = create_filter_analysis_app(
        gateway_url=config.filter_analysis_worker.gateway_url,
        port=config.filter_analysis_worker.port,
    )

    logger.info(f"Starting filter-analysis worker on {config.filter_analysis_worker.host}:{config.filter_analysis_worker.port}")
    uvicorn.run(app, host=config.filter_analysis_worker.host, port=config.filter_analysis_worker.port)


def run_decision_worker(config: AppConfig):
    from src.workers.decision import create_decision_app

    logger = get_logger("main.decision_worker")
    app = create_decision_app(
        gateway_url=config.decision_worker.gateway_url,
        port=config.decision_worker.port,
        feishu_app_id=config.feishu.app_id,
        feishu_app_secret=config.feishu.app_secret,
        feishu_webhook_url=config.feishu.webhook_url,
        feishu_user_id=config.feishu.user_id,
        feishu_use_websocket=config.feishu.use_websocket,
    )

    logger.info(f"Starting decision worker on {config.decision_worker.host}:{config.decision_worker.port}")
    uvicorn.run(app, host=config.decision_worker.host, port=config.decision_worker.port)


def run_execution_worker(config: AppConfig):
    from src.workers.execution import create_execution_app

    logger = get_logger("main.execution_worker")
    app = create_execution_app(
        gateway_url=config.execution_worker.gateway_url,
        port=config.execution_worker.port,
        api_url=config.execution_worker.opencode_api_url or config.opencode.api_url,
        work_dir=config.execution_worker.work_dir,
        timeout=config.execution_worker.timeout,
        model_provider=config.execution_worker.model_provider,
        model_id=config.execution_worker.model_id,
    )

    logger.info(f"Starting execution worker on {config.execution_worker.host}:{config.execution_worker.port}")
    uvicorn.run(app, host=config.execution_worker.host, port=config.execution_worker.port)


def run_recording_worker(config: AppConfig):
    from src.workers.recording import create_recording_app

    logger = get_logger("main.recording_worker")
    app = create_recording_app(
        gateway_url=config.recording_worker.gateway_url,
        port=config.recording_worker.port,
        feishu_app_id=config.feishu.app_id,
        feishu_app_secret=config.feishu.app_secret,
        feishu_table_id=config.feishu.table_id,
        feishu_webhook_url=config.feishu.webhook_url,
    )

    logger.info(f"Starting recording worker on {config.recording_worker.host}:{config.recording_worker.port}")
    uvicorn.run(app, host=config.recording_worker.host, port=config.recording_worker.port)


def run_listener(config: AppConfig):
    import asyncio

    logger = get_logger("main.listener")

    from src.listener_push import PushClient
    from src.wechat_listener.factory import ListenerFactory
    from src.wechat_listener.base import ListenerType, Platform, MessageCallback

    push_client = PushClient(
        gateway_url=config.listener_push.gateway_url,
        timeout=config.listener_push.timeout,
        max_retries=config.listener_push.max_retries,
        retry_delay=config.listener_push.retry_delay,
    )

    async def on_message_callback(message):
        logger.info(f"Message received: {message.content[:50] if message.content else ''}...")
        try:
            from datetime import datetime

            result = await push_client.push_message(
                content=message.content,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                conversation_id=message.conversation_id,
                conversation_type="group" if message.conversation_type.value == "group" else "private",
                msg_id=message.msg_id,
                msg_type=message.msg_type.value if hasattr(message.msg_type, "value") else "text",
                platform=config.wechat.platform,
                listener_type=config.wechat.listener_type,
                timestamp=datetime.now().isoformat(),
            )
            logger.info(f"Push result: {result.get('code')} - task_id: {result.get('task_id')}")
        except Exception as e:
            logger.error(f"Error pushing message: {e}")

    async def _run():
        try:
            listener_type = ListenerType(config.wechat.listener_type)
            platform = Platform(config.wechat.platform)
            if listener_type == ListenerType.OCR:
                listener = ListenerFactory.create(
                    listener_type=listener_type,
                    platform=platform,
                    keywords=config.task_filters.keywords,
                    regex_patterns=config.task_filters.regex_patterns,
                    poll_interval=config.wechat.ocr.poll_interval,
                    crop_ratio=tuple(config.wechat.ocr.crop_ratio),
                    message_region_height=config.wechat.ocr.message_region_height,
                )
            elif listener_type == ListenerType.NTWORK:
                listener = ListenerFactory.create(
                    listener_type=listener_type,
                    platform=platform,
                    keywords=config.task_filters.keywords,
                    regex_patterns=config.task_filters.regex_patterns,
                    device_id=config.wechat.ntwork.device_id,
                    ip=config.wechat.ntwork.ip,
                    port=config.wechat.ntwork.port,
                    smart_mode=config.wechat.ntwork.smart_mode,
                )
            elif listener_type == ListenerType.UIAUTOMATION:
                listener = ListenerFactory.create(
                    listener_type=listener_type,
                    platform=platform,
                    keywords=config.task_filters.keywords,
                    regex_patterns=config.task_filters.regex_patterns,
                    poll_interval=config.wechat.uiautomation.poll_interval,
                    max_history=config.wechat.uiautomation.max_history,
                )
            else:
                listener = ListenerFactory.create(
                    listener_type=listener_type,
                    platform=platform,
                    keywords=config.task_filters.keywords,
                    regex_patterns=config.task_filters.regex_patterns,
                )
        except Exception as e:
            logger.error(f"Failed to create listener: {e}")
            sys.exit(1)

        listener.set_callback(MessageCallback(on_message=on_message_callback))

        try:
            await listener.connect()
            logger.info("Listener connected successfully")
            listener.start_background()
            logger.info("Listener started in background, pushing to gateway")

            while listener.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down listener...")
            listener.disconnect()
        except Exception as e:
            logger.error(f"Failed to start listener: {e}")
            sys.exit(1)

    asyncio.run(_run())


def main():
    args = parse_args()

    try:
        config_manager = ConfigManager(config_path=args.config) if args.config else ConfigManager()
        config = config_manager.config
    except FileNotFoundError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    setup_logger(
        log_dir=config.logging.dir,
        log_level=args.log_level or config.logging.level,
    )

    logger = get_logger("main")
    logger.info("=" * 50)
    logger.info("WeChat Task Automation System v2")
    logger.info("=" * 50)
    logger.info(f"Mode: {args.mode}")

    runners = {
        "standalone": run_standalone,
        "gateway": run_gateway,
        "filter-analysis": run_filter_analysis_worker,
        "decision": run_decision_worker,
        "execution": run_execution_worker,
        "recording": run_recording_worker,
        "listener": run_listener,
    }

    runner = runners.get(args.mode)
    if runner is None:
        logger.error(f"Unknown mode: {args.mode}")
        sys.exit(1)

    if args.mode == "standalone":
        runner(config, dry_run=args.dry_run)
    else:
        runner(config)


if __name__ == "__main__":
    main()
