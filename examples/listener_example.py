"""Example usage of the new listener system."""

import asyncio
from src.wechat_listener import (
    ListenerFactory,
    ListenerType,
    Platform,
    MessageCallback,
)
from src.config.config_manager import ConfigManager


async def main():
    config = ConfigManager()
    
    listener = ListenerFactory.create(
        listener_type=ListenerType.UIAUTOMATION,
        platform=Platform.WEWORK,
        keywords=config.task_filters.keywords,
        regex_patterns=config.task_filters.regex_patterns,
        poll_interval=config.wechat.uiautomation.poll_interval,
        max_history=config.wechat.uiautomation.max_history,
    )
    
    def on_message(msg):
        print(f"收到消息: {msg.content}")
    
    def on_task_message(task):
        print(f"收到任务消息: {task.raw_text}")
        print(f"匹配关键词: {task.keywords_matched}")
    
    def on_error(err):
        print(f"发生错误: {err}")
    
    callback = MessageCallback(
        on_message=on_message,
        on_task_message=on_task_message,
        on_error=on_error,
    )
    
    listener.set_callback(callback)
    
    try:
        await listener.connect()
        print("监听器已连接，开始监听消息...")
        await listener.start_listening()
    except KeyboardInterrupt:
        print("正在停止监听...")
    finally:
        listener.disconnect()


def create_listener_from_config():
    """Example: Create listener from config file."""
    config = ConfigManager()
    
    listener_config = {
        "listener_type": config.wechat.listener_type,
        "platform": config.wechat.platform,
        "keywords": config.task_filters.keywords,
        "regex_patterns": config.task_filters.regex_patterns,
        config.wechat.listener_type: {
            "poll_interval": config.wechat.uiautomation.poll_interval,
            "max_history": config.wechat.uiautomation.max_history,
        },
    }
    
    return ListenerFactory.create_from_config(listener_config)


if __name__ == "__main__":
    asyncio.run(main())
