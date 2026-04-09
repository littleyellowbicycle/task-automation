"""
测试完整工作流程

使用方法:
python tests/test_workflow.py
"""

import os
import sys
import asyncio
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.queue import TaskQueue, QueueConfig
from src.executor import CodeExecutor, ExecutorConfig
from src.feishu_recorder import FeishuClient
from src.callback_server import CallbackServer


async def test_complete_workflow():
    """测试完整的工作流程"""
    print("\n" + "=" * 60)
    print("完整工作流程测试")
    print("=" * 60)
    
    # 1. 初始化组件
    print("\n[步骤 1] 初始化组件...")
    
    queue_config = QueueConfig(max_size=5, confirmation_timeout=60)
    task_queue = TaskQueue(queue_config)
    
    executor_config = ExecutorConfig.from_env()
    executor = CodeExecutor(executor_config)
    
    feishu_client = FeishuClient()
    
    callback_server = CallbackServer(port=8082)
    callback_server.set_task_queue(task_queue)
    callback_server.set_feishu_client(feishu_client)
    
    print("  [OK] 组件初始化完成")
    
    # 2. 模拟任务入队
    print("\n[步骤 2] 模拟任务入队...")
    
    task_data = {
        "summary": "创建一个简单的 Python 脚本",
        "raw_message": "请帮我创建一个名为 hello_workflow.py 的文件，内容是 print('Hello from workflow test!')",
        "tech_stack": ["Python"],
        "core_features": ["文件创建"],
    }
    
    task_id = task_queue.enqueue("test_workflow_001", task_data)
    print(f"  [OK] 任务已入队: {task_id}")
    
    # 3. 模拟处理任务
    print("\n[步骤 3] 模拟处理任务...")
    
    task = task_queue.dequeue(timeout=5)
    if task:
        print(f"  任务 ID: {task.task_id}")
        print(f"  摘要: {task.data.get('summary')}")
        
        # 4. 模拟用户确认
        print("\n[步骤 4] 模拟用户确认...")
        decision = "approve"
        task.metadata["decision"] = decision
        print(f"  [OK] 用户确认: {decision}")
        
        # 5. 执行任务
        print("\n[步骤 5] 执行任务...")
        result = executor.execute(
            instruction=task.data.get("raw_message"),
            task_id=task.task_id,
            dry_run=True,
        )
        print(f"  状态: {result.status}")
        print(f"  成功: {result.success}")
        
        # 6. 模拟创建飞书记录
        print("\n[步骤 6] 模拟创建飞书记录...")
        # (实际使用时会在用户确认后创建)
        
        # 7. 模拟更新状态
        print("\n[步骤 7] 模拟更新状态...")
        
        # 8. 模拟发送完成通知
        print("\n[步骤 8] 模拟发送完成通知...")
        
        # 9. 清理
        print("\n[步骤 9] 清理测试数据...")
        task_queue.cancel_task(task_id, reason="Test completed")
        print(f"  [OK] 任务已取消")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    print("\n工作流程说明:")
    print("  1. 任务入队 -> 等待处理")
    print("  2. 任务出队 -> 发送确认请求")
    print("  3. 用户确认 -> 创建飞书记录 -> 执行任务")
    print("  4. 执行完成 -> 更新状态 -> 发送通知")
    print("  5. 用户取消 -> 不创建记录 -> 任务移除")
    print("  6. 用户稍后 -> 放回队列尾部 -> 等待下次处理")


if __name__ == "__main__":
    asyncio.run(test_complete_workflow())
