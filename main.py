"""Main entry point for WeChat Task Automation System."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.workflow_orchestrator import WorkflowOrchestrator
from src.wechat_listener import WeChatListener
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
    from src.wechat_listener.models import WeChatMessage, MessageType, ConversationType
    from datetime import datetime
    
    # Create mock task message
    mock_message = WeChatMessage(
        msg_id="test_001",
        msg_type=MessageType.TEXT,
        content="项目发布：开发一个用户登录功能，使用 Python Flask 框架",
        conversation_id="R:group_001",
        conversation_type=ConversationType.GROUP,
        sender_id="user_001",
        sender_name="Test User",
        timestamp=datetime.now(),
    )
    
    from src.wechat_listener.models import TaskMessage
    task_message = TaskMessage(
        original_message=mock_message,
        is_project_task=True,
        keywords_matched=["项目发布"],
        confidence_score=0.5,
    )
    
    # Run workflow
    result = await orchestrator.run(task_message)
    print(f"\n✅ Workflow completed!")
    print(f"Task ID: {result.task_id}")
    print(f"Summary: {result.summary}")
    print(f"Status: {result.status.value}")
    print(f"Tech Stack: {result.tech_stack}")
    print(f"Core Features: {result.core_features}")
    
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
        log_dir=config.logging.dir,
        log_level=args.log_level or config.logging.level,
    )
    logger = get_logger("main")
    
    logger.info("=" * 50)
    logger.info("WeChat Task Automation System")
    logger.info("=" * 50)
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Initialize workflow orchestrator
    orchestrator = WorkflowOrchestrator(
        dry_run=args.dry_run or args.mode in ["test", "mock"],
    )
    
    if args.mode in ["test", "mock"]:
        logger.info("Running in test/mock mode...")
        result = await test_workflow(orchestrator)
        logger.info("Test completed successfully!")
        return
    
    # Normal mode: Start listening for WeChat messages
    logger.info("Starting WeChat listener...")
    
    # Create WeChat listener
    listener = WeChatListener(
        device_id=config.wechat.device_id,
        ip=config.wechat.ip,
        port=config.wechat.port,
        keywords=config.task_filters.keywords,
        regex_patterns=config.task_filters.regex_patterns,
    )
    
    # Set up callback
    from src.wechat_listener.models import TaskMessage
    
    async def on_task_message(task_msg: TaskMessage):
        logger.info(f"Task message received: {task_msg.original_message.content[:50]}...")
        try:
            result = await orchestrator.run(task_msg)
            logger.info(f"Task completed: {result.task_id} - {result.status.value}")
        except Exception as e:
            logger.error(f"Workflow error: {e}")
    
    from src.wechat_listener.listener import MessageCallback
    listener.set_callback(MessageCallback(on_task_message=on_task_message))
    
    # Start listening
    try:
        await listener.start_listening()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        listener.disconnect()


def main():
    """Main entry point."""
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
