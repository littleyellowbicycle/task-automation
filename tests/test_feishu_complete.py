"""
Complete Feishu card test with callback server.
Note: You need to expose the callback server to public internet using ngrok or similar tool.

Usage:
1. Install ngrok: https://ngrok.com/
2. Run: ngrok http 8086
3. Copy the public URL (e.g., https://xxx.ngrok.io)
4. Run this script with the public URL
"""
import sys
import os
import time
import threading
import asyncio
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
import requests
from src.callback_server import CallbackServer
from src.feishu_recorder.client import FeishuClient
from src.executor import create_executor, ExecutorConfig
from dotenv import load_dotenv

load_dotenv()


def run_callback_server(app, port):
    """Run callback server in a thread."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def main():
    print("=" * 70)
    print("  Feishu Card -> User Click -> OpenCode Execution Test")
    print("=" * 70)
    
    public_url = os.getenv("PUBLIC_CALLBACK_URL", "")
    if not public_url:
        print("\n⚠️  WARNING: PUBLIC_CALLBACK_URL not set!")
        print("   The card buttons will use localhost URL which won't work from Feishu.")
        print("   To test with real Feishu card clicks:")
        print("   1. Install ngrok: https://ngrok.com/")
        print("   2. Run: ngrok http 8086")
        print("   3. Set PUBLIC_CALLBACK_URL=https://xxx.ngrok.io in .env")
        print("\n   For now, using localhost for testing...")
        public_url = "http://localhost:8086"
    
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
    print(f"    ✅ Server started")
    print(f"    Public URL: {public_url}")
    
    print("\n[2] Creating Feishu client...")
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET"),
        table_id=os.getenv("FEISHU_TABLE_ID"),
        callback_url=public_url,
    )
    
    user_id = os.getenv("FEISHU_USER_ID", "a5566bge")
    print(f"    User ID: {user_id}")
    
    task_id = f"feishu_task_{int(time.time())}"
    
    print(f"\n[3] Creating task...")
    print(f"    Task ID: {task_id}")
    print(f"    Summary: 创建Python计算器脚本")
    
    print(f"\n[4] Sending approval card to Feishu...")
    
    card = {
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
                    "content": "**任务摘要**\n创建Python计算器脚本，包括加减乘除功能"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**技术栈**: Python"
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
                            "content": "✅ 确认执行"
                        },
                        "type": "primary",
                        "url": f"{public_url}/decision?task_id={task_id}&action=approve"
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "❌ 取消"
                        },
                        "type": "danger",
                        "url": f"{public_url}/decision?task_id={task_id}&action=reject"
                    }
                ]
            }
        ]
    }
    
    message_id = feishu_client.send_private_message(
        user_id=user_id,
        content=card,
        msg_type="interactive",
    )
    
    if message_id:
        print(f"    ✅ Card sent successfully!")
        print(f"    Message ID: {message_id}")
        print(f"\n    📱 请在飞书中查看卡片并点击确认按钮")
        if "localhost" in public_url:
            print(f"\n    ⚠️  由于使用localhost，飞书客户端无法访问回调URL")
            print(f"    您可以手动访问以下URL来模拟确认:")
            print(f"    {public_url}/decision?task_id={task_id}&action=approve")
    else:
        print(f"    ❌ Failed to send card")
        return
    
    print(f"\n[5] Waiting for your decision (180 seconds)...")
    
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
                "创建一个Python计算器脚本calculator.py，实现加减乘除功能",
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
            
        else:
            print(f"\n[7] Unknown decision: {decision}")
            
    except asyncio.TimeoutError:
        print(f"\n⏱️ Timeout: No decision received within 180 seconds")
    
    print("\n" + "=" * 70)
    print("  Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
