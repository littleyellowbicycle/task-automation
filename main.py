"""Main entry point for WeChat Task Automation System."""

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.workflow_orchestrator import WorkflowOrchestrator
from src.wechat_listener.factory import ListenerFactory
from src.wechat_listener.base import ListenerType, Platform
from src.monitoring import initialize_monitoring, MetricConfig, AlertConfig
from src.feishu_recorder.feishu_bridge import FeishuBridge
from src.feishu_recorder.server import create_feishu_server
from src.utils import setup_logger, get_logger


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="WeChat Task Automation System"
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "test", "mock"],
        default="normal",
        help="Run mode (default: normal)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually execute code generation"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config.yaml"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    return parser.parse_args()


async def test_workflow(orchestrator: WorkflowOrchestrator):
    """Run a test workflow with mock message."""
    from datetime import datetime
    
    # Create mock raw message
    raw_message = {
        "msg_id": "test_001",
        "content": "项目发布：开发一个用户登录功能，使用 Python Flask 框架",
        "sender_id": "user_001",
        "sender_name": "Test User",
        "conversation_id": "R:group_001",
        "conversation_type": "group",
        "timestamp": datetime.now(),
        "msg_type": "text",
    }
    
    # Process through workflow
    result = await orchestrator.process_raw_message(raw_message)
    print(f"\n=== Workflow test completed! ===")
    if result:
        print(f"Message processed: {result.msg_id}")
        print(f"Content: {result.content[:100]}...")
    else:
        print("Message was filtered out")
    
    return result


async def main_async(args):
    """Async main function."""
    # Load configuration
    try:
        config = ConfigManager(config_path=args.config) if args.config else ConfigManager()
    except FileNotFoundError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Setup logging
    setup_logger(
        log_dir=config.logging_dir,
        log_level=args.log_level or config.logging_level,
    )
    logger = get_logger("main")
    
    logger.info("=" * 50)
    logger.info("WeChat Task Automation System")
    logger.info("=" * 50)
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Initialize monitoring service
    metric_config = MetricConfig(
        enabled=config.monitoring.enabled,
        prometheus_port=config.monitoring.prometheus_port,
        metrics_retention=config.monitoring.metrics_retention,
        log_retention_days=config.monitoring.log_retention_days
    )
    
    alert_config = AlertConfig(
        enabled=config.monitoring.enabled,
        feishu_webhook=config.monitoring.alert_webhook,
        queue_threshold=config.monitoring.queue_threshold,
        failure_threshold=config.monitoring.failure_threshold,
        llm_timeout_threshold=30,
        resource_threshold=90.0,
        service_failure_threshold=3
    )
    
    monitoring = initialize_monitoring(metric_config, alert_config)
    asyncio.create_task(monitoring.start())
    logger.info("Monitoring service initialized")
    
    # Initialize Feishu bridge
    feishu_bridge = FeishuBridge(
        app_id=config.feishu.app_id,
        app_secret=config.feishu.app_secret,
        table_id=config.feishu.table_id,
        webhook_url=config.feishu.webhook_url
    )
    
    # Start Feishu callback server
    feishu_server = create_feishu_server(
        host="0.0.0.0",
        port=8000,
        feishu_bridge=feishu_bridge
    )
    feishu_server.start()
    logger.info("Feishu callback server initialized")
    
    # Initialize workflow orchestrator
    orchestrator = WorkflowOrchestrator(
        feishu_bridge=feishu_bridge,
        dry_run=args.dry_run or args.mode in ["test", "mock"],
    )
    
    if args.mode in ["test", "mock"]:
        logger.info("Running in test/mock mode...")
        result = await test_workflow(orchestrator)
        logger.info("Test completed successfully!")
        return
    
    # Normal mode: Start listening for WeChat messages
    logger.info("Starting WeChat listener...")
    logger.info(f"Listener type: {config.wechat.listener_type}")
    logger.info(f"Platform: {config.wechat.platform}")

    # Create listener using factory
    try:
        listener_type = ListenerType(config.wechat.listener_type)
        platform = Platform(config.wechat.platform)
        listener = ListenerFactory.create(
            listener_type=listener_type,
            platform=platform,
            keywords=config.task_filters.keywords,
            regex_patterns=config.task_filters.regex_patterns,
            poll_interval=config.wechat.uiautomation.poll_interval,
            max_history=config.wechat.uiautomation.max_history,
        )
    except Exception as e:
        logger.error(f"Failed to create listener: {e}")
        sys.exit(1)

    # Set up message callback
    from src.wechat_listener.base import MessageCallback
    
    async def on_message_callback(message):
        logger.info(f"Message received: {message.content[:50] if message.content else ''}...")
        try:
            raw_message = {
                "msg_id": message.msg_id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": message.sender_name,
                "conversation_id": message.conversation_id,
                "conversation_type": "group" if message.conversation_type.value == "group" else "private",
                "timestamp": message.timestamp,
                "msg_type": message.msg_type.value if hasattr(message.msg_type, 'value') else "text",
            }
            await orchestrator.process_raw_message(
                raw_message,
                platform=config.wechat.platform,
                listener_type=config.wechat.listener_type
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    listener.set_callback(MessageCallback(on_message=on_message_callback))

    # Start listening
    try:
        await listener.connect()
        logger.info("Listener connected successfully")
        
        listener.start_background()
        logger.info("Listener started in background")
        
        while listener.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        listener.disconnect()
    except Exception as e:
        logger.error(f"Failed to start listener: {e}")
        logger.error("Make sure WeChat/WeWork is running and visible")
        sys.exit(1)


def main():
    """Main entry point."""
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
