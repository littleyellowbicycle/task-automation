"""
Test real Feishu card approval flow.
Sends a real Feishu card to user and waits for approval.
"""
import sys
import os
import time
import threading
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from src.callback_server import CallbackServer
from src.feishu_recorder.client import FeishuClient
from src.feishu_recorder.models import TaskRecord, TaskStatus
from src.executor import create_executor, ExecutorConfig
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def run_callback_server(app, port):
    """Run callback server in a thread."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def main():
    print("=" * 70)
    print("  Real Feishu Card Test: Send Card -> User Click -> Execute")
    print("=" * 70)
    
    port = 8086
    callback_server = CallbackServer(host="0.0.0.0", port=port)
    
    print(f"\n[1] Starting callback server on port {port}...")
    thread = threading.Thread(
        target=run_callback_server,
        args=(callback_server.app, port),
        daemon=True
    )
    thread.start()
    time.sleep(2)
    print("    ✅ Server started")
    
    callback_url = f"http://localhost:{port}"
    print(f"    Callback URL: {callback_url}")
    
    print("\n[2] Creating Feishu client...")
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET"),
        table_id=os.getenv("FEISHU_TABLE_ID"),
        callback_url=callback_url,
    )
    
    user_id = os.getenv("FEISHU_USER_ID", "a5566bge")
    print(f"    User ID: {user_id}")
    
    task_id = f"feishu_test_{int(time.time())}"
    
    print(f"\n[3] Creating task record...")
    task_record = TaskRecord(
        task_id=task_id,
        raw_message="创建一个Python脚本，实现简单的计算器功能，包括加减乘除运算",
        summary="创建Python计算器脚本",
        tech_stack=["Python"],
        core_features=["add", "subtract", "multiply", "divide"],
        status=TaskStatus.PENDING,
        user_id=user_id,
        user_name="Test User",
        created_at=datetime.now(timezone.utc),
    )
    print(f"    Task ID: {task_id}")
    print(f"    Summary: {task_record.summary}")
    
    print(f"\n[4] Sending approval card to Feishu...")
    
    import json
    
    card_content = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"任务审批: {task_id}"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**任务摘要**\n{task_record.summary}"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**技术栈**: {', '.join(task_record.tech_stack)}"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "确认执行"
                        },
                        "type": "primary",
                        "url": f"{callback_url}/decision?task_id={task_id}&action=approve"
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "取消"
                        },
                        "type": "danger",
                        "url": f"{callback_url}/decision?task_id={task_id}&action=reject"
                    }
                ]
            }
        ]
    }
    
    message_id = feishu_client.send_private_message(
        user_id=user_id,
        content=json.dumps({
            "type": "interactive",
            "card": card_content
        }),
        msg_type="interactive",
    )
    
    if message_id:
        print(f"    ✅ Card sent successfully!")
        print(f"    Message ID: {message_id}")
        print(f"\n    📱 请在飞书中查看卡片并点击确认按钮")
        print(f"    ⚠️ 注意: 回调URL是 {callback_url}")
        print(f"    ⚠️ 如果您的机器没有公网IP，飞书可能无法访问回调URL")
    else:
        print(f"    ❌ Failed to send card")
        print(f"    请检查飞书配置是否正确")
        return
    
    print(f"\n[5] Waiting for your decision (180 seconds)...")
    print(f"    点击卡片上的按钮来确认或取消任务")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        decision = loop.run_until_complete(
            asyncio.wait_for(
                callback_server.wait_for_decision(task_id),
                timeout=180
            )
        )
        
        print(f"\n[6] Decision received: {decision}")
        
        if decision == "approve":
            print(f"\n[7] Executing task with OpenCode...")
            
            config = ExecutorConfig(
                backend="opencode",
                mode="api",
                api_url="http://localhost:4096",
                work_dir="./workspace",
                model_provider="opencode",
                model_id="minimax-m2.5-free",
                timeout=300,
            )
            
            executor = create_executor(config)
            
            print("    Sending task to OpenCode...")
            
            result = executor.execute(
                f"创建代码: {task_record.summary}",
                task_id=task_id,
            )
            
            print(f"\n[8] Result:")
            print(f"    Success:  {result.success}")
            print(f"    Status:   {result.status}")
            print(f"    Duration: {result.duration:.2f}s")
            if result.files_created:
                print(f"    Files:    {result.files_created}")
            if result.error_message:
                print(f"    Error:    {result.error_message}")
                
        elif decision == "reject":
            print(f"\n[7] Task rejected. Cancelled.")
            
        elif decision == "later":
            print(f"\n[7] Task deferred.")
            
        else:
            print(f"\n[7] Unknown decision: {decision}")
            
    except asyncio.TimeoutError:
        print(f"\n⏱️ Timeout: No decision received within 180 seconds")
    
    print("\n" + "=" * 70)
    print("  Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
