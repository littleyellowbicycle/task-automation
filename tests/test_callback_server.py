"""
测试回调服务

使用方法:
1. 启动服务: python tests/test_callback_server.py
2. 访问 http://localhost:8082/decision?task_id=test123&action=approve 测试

流程说明:
- 任务先进入队列，等待用户确认
- 用户确认后才创建飞书表格记录
- 用户取消则不创建记录
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.callback_server import CallbackServer, Decision
from src.queue import TaskQueue, QueueConfig
from src.feishu_recorder import FeishuClient


def create_test_queue():
    config = QueueConfig(max_size=20, confirmation_timeout=10800)
    queue = TaskQueue(config)
    
    queue.enqueue(
        "test123",
        {
            "summary": "测试任务",
            "raw_message": "这是一个测试任务，用于验证飞书对接",
            "tech_stack": ["Python", "FastAPI"],
            "core_features": ["测试功能"],
        }
    )
    queue.enqueue(
        "task456",
        {
            "summary": "另一个任务",
            "raw_message": "这是另一个测试任务",
            "tech_stack": ["Python"],
            "core_features": ["功能A", "功能B"],
        }
    )
    
    return queue


async def on_approved(task_id: str):
    print(f"\n✅ 任务 {task_id} 已确认")
    print(f"   → 创建飞书表格记录")
    print(f"   → 调用执行器处理任务")


async def on_rejected(task_id: str):
    print(f"\n❌ 任务 {task_id} 已取消")
    print(f"   → 不创建飞书记录")
    print(f"   → 任务从队列中移除")


async def on_later(task_id: str):
    print(f"\n⏸️ 任务 {task_id} 已放回队列尾部")
    print(f"   → 等待下次处理")


if __name__ == "__main__":
    queue = create_test_queue()
    feishu_client = FeishuClient()
    
    server = CallbackServer(host="0.0.0.0", port=8082)
    server.set_task_queue(queue)
    server.set_feishu_client(feishu_client)
    server.on_approved(on_approved)
    server.on_rejected(on_rejected)
    server.on_later(on_later)
    
    print("\n" + "=" * 60)
    print("回调服务启动")
    print("=" * 60)
    print(f"\n📋 正确的任务流程:")
    print(f"   1. 任务进入队列 (PENDING)")
    print(f"   2. 发送确认卡片到飞书")
    print(f"   3. 用户确认 → 创建表格记录 → 开始执行")
    print(f"   4. 用户取消 → 不创建记录 → 任务移除")
    
    print(f"\n本地测试地址:")
    print(f"  - 健康检查: http://localhost:8082/health")
    print(f"  - 队列状态: http://localhost:8082/queue/status")
    print(f"  - 确认任务: http://localhost:8082/decision?task_id=test123&action=approve")
    print(f"  - 取消任务: http://localhost:8082/decision?task_id=test123&action=reject")
    print(f"  - 稍后处理: http://localhost:8082/decision?task_id=test123&action=later")
    print(f"  - 飞书回调: http://localhost:8082/feishu/callback")
    
    print(f"\n决策处理流程:")
    print(f"  ✅ approve → 创建表格记录，开始执行")
    print(f"  ❌ reject  → 不创建记录，任务移除")
    print(f"  ⏸️ later   → 任务放回队列尾部，稍后处理")
    
    print(f"\n内网穿透配置:")
    print(f"  1. 安装 ngrok: https://ngrok.com/download")
    print(f"  2. 运行: ngrok http 8082")
    print(f"  3. 将 ngrok 提供的 URL 配置到 FEISHU_CALLBACK_URL")
    print("=" * 60 + "\n")
    
    server.run()
