"""
Quick demo script for UIAutomation listener.

Run this script to test the UIAutomation listener.
Make sure WeChat/WeCom is running and visible before running.
"""

import asyncio
import sys

sys.path.insert(0, ".")

from src.wechat_listener import (
    ListenerFactory,
    ListenerType,
    Platform,
    MessageCallback,
)
from src.config.config_manager import ConfigManager


async def demo():
    print("=" * 60)
    print("UIAutomation Listener Demo")
    print("=" * 60)
    print()
    
    config = ConfigManager()
    
    print(f"配置监听器类型: {config.wechat.listener_type}")
    print(f"配置平台: {config.wechat.platform}")
    print(f"任务关键词: {config.task_filters.keywords}")
    print()
    
    listener = ListenerFactory.create(
        listener_type=ListenerType.UIAUTOMATION,
        platform=Platform.WEWORK,
        keywords=config.task_filters.keywords,
        regex_patterns=config.task_filters.regex_patterns,
        poll_interval=config.wechat.uiautomation.poll_interval,
        max_history=config.wechat.uiautomation.max_history,
    )
    
    message_count = 0
    task_count = 0
    
    def on_message(msg):
        nonlocal message_count
        message_count += 1
        print(f"[消息 #{message_count}] {msg.sender_name}: {msg.content[:50]}...")
    
    def on_task_message(task):
        nonlocal task_count
        task_count += 1
        print(f"[任务 #{task_count}] 检测到任务!")
        print(f"  内容: {task.raw_text[:100]}...")
        print(f"  匹配关键词: {task.keywords_matched}")
        print()
    
    def on_error(err):
        print(f"[错误] {err}")
    
    callback = MessageCallback(
        on_message=on_message,
        on_task_message=on_task_message,
        on_error=on_error,
    )
    
    listener.set_callback(callback)
    
    print("正在连接到微信窗口...")
    print("请确保企业微信或微信已打开并可见")
    print()
    
    try:
        success = await listener.connect()
        if success:
            print("✓ 连接成功!")
            print()
            print("开始监听消息 (按 Ctrl+C 停止)...")
            print("-" * 60)
            print()
            
            await listener.start_listening()
            
    except KeyboardInterrupt:
        print()
        print("-" * 60)
        print("正在停止监听...")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        print()
        print("请检查:")
        print("  1. 微信/企业微信是否已启动")
        print("  2. 微信窗口是否可见（未最小化）")
        print("  3. 是否已安装 uiautomation: pip install uiautomation")
    finally:
        listener.disconnect()
        print()
        print(f"统计: 共收到 {message_count} 条消息，其中 {task_count} 条任务消息")
        print("已断开连接")


if __name__ == "__main__":
    asyncio.run(demo())
