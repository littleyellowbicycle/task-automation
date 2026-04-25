"""
Test script for OCR listener with enterprise WeChat.

Steps:
1. Make sure WeCom (企业微信) is running and visible
2. Open a group chat in WeCom
3. Run this script
4. Send a test message in the group
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, ".")

os.environ["COMTYPES_CACHE_DIR"] = os.path.join(tempfile.gettempdir(), "comtypes_cache")
os.makedirs(os.environ["COMTYPES_CACHE_DIR"], exist_ok=True)

MODEL_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "models", "paddleocr"))
os.makedirs(MODEL_BASE, exist_ok=True)

import paddleocr
paddleocr.paddleocr.BASE_DIR = MODEL_BASE

from src.wechat_listener.listeners.ocr_listener import OCRListener
from src.wechat_listener.base import Platform, MessageCallback


async def test():
    print("=" * 60)
    print("企业微信 OCR 监听器测试")
    print("=" * 60)
    print()

    listener = OCRListener(
        platform=Platform.WEWORK,
        poll_interval=2.0,
        keywords=["项目发布", "需求", "开发任务", "功能开发", "bug修复", "重构"],
        crop_ratio=(0.22, 0.0, 1.0, 0.92),
    )

    message_count = 0
    task_count = 0

    def on_message(msg):
        nonlocal message_count
        message_count += 1
        conv_type = "群聊" if msg.is_group_message else "私聊"
        sender = msg.sender_name or "unknown"
        print(f"\n[消息 #{message_count}] ({conv_type}) {sender}: {msg.content}")

    def on_task_message(task):
        nonlocal task_count
        task_count += 1
        print(f"  >>> 检测到任务! 关键词: {task.keywords_matched}, 置信度: {task.confidence_score}")

    def on_error(err):
        print(f"[错误] {err}")

    callback = MessageCallback(
        on_message=on_message,
        on_task_message=on_task_message,
        on_error=on_error,
    )
    listener.set_callback(callback)

    print("Step 1: 连接企业微信窗口...")
    try:
        success = await listener.connect()
        if not success:
            print("连接失败!")
            return
        print("  连接成功!")
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    print(f"\nStep 2: 窗口区域: {listener._window_rect}")

    print("\nStep 3: 测试截图 + OCR 识别...")
    screenshot = listener._capture_message_region()
    if screenshot and screenshot.size[0] > 0 and screenshot.size[1] > 0:
        screenshot_path = os.path.join(tempfile.gettempdir(), "wecom_ocr_test.png")
        try:
            screenshot.save(screenshot_path)
            print(f"  截图已保存: {screenshot_path}")
        except Exception as e:
            print(f"  截图保存失败: {e}")
        print(f"  截图尺寸: {screenshot.size}")

        lines = listener._ocr_extract(screenshot)
        print(f"  OCR 识别到 {len(lines)} 行文字:")
        for i, line in enumerate(lines[:20]):
            print(f"    {i + 1}. [{line['confidence']:.2f}] {line['text']}")

        messages = listener._group_lines_into_messages(lines)
        print(f"\n  解析出 {len(messages)} 条消息:")
        for i, msg in enumerate(messages[:10]):
            sender = msg['sender'] or '(无发送人)'
            print(f"    {i + 1}. {sender}: {msg['content'][:60]}")
    else:
        print("  截图失败!")

    print("\nStep 4: 开始持续监听 (按 Ctrl+C 停止)...")
    print("-" * 60)
    print("提示: 在企业微信群聊中发送消息，观察是否被捕获")
    print("      包含关键词的消息会被标记为任务")
    print()

    listener.start_background()

    try:
        while True:
            task_msg = await listener.get_next_message(timeout=1.0)
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n停止监听...")
    finally:
        listener.disconnect()
        print(f"\n统计: 共收到 {message_count} 条消息，其中 {task_count} 条任务消息")


if __name__ == "__main__":
    asyncio.run(test())
