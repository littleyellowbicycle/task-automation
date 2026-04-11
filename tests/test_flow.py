"""
Test Feishu card flow - keeps running until decision is made.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import threading
import asyncio
from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 70)
    print("  Feishu Card Flow Test with ngrok Tunnel")
    print("=" * 70)
    
    public_url = os.getenv("PUBLIC_CALLBACK_URL", "")
    if not public_url:
        print("\n❌ PUBLIC_CALLBACK_URL not set in .env")
        return
    
    print(f"\n[1] Public URL: {public_url}")
    
    from src.callback_server import CallbackServer
    from src.feishu_recorder.client import FeishuClient
    from src.executor import create_executor, ExecutorConfig
    import uvicorn
    
    port = 8086
    callback_server = CallbackServer(host="0.0.0.0", port=port)
    
    print(f"\n[2] Starting callback server on port {port}...")
    
    def run_server():
        uvicorn.run(callback_server.app, host="0.0.0.0", port=port, log_level="warning")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)
    print("    ✅ Callback server started")
    
    print(f"\n[3] Creating Feishu client...")
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET"),
        table_id=os.getenv("FEISHU_TABLE_ID"),
        callback_url=public_url,
    )
    
    user_id = os.getenv("FEISHU_USER_ID", "a5566bge")
    task_id = f"ngrok_test_{int(time.time())}"
    
    print(f"\n[4] Sending approval card to Feishu...")
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"Task: {task_id}"},
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "**Task**\nCreate Python calculator"}
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**URL**: {public_url}"}
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "Approve"},
                        "type": "primary",
                        "url": f"{public_url}/decision?task_id={task_id}&action=approve"
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "Reject"},
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
        print(f"    ✅ Card sent!")
        print(f"    Message ID: {message_id}")
    else:
        print(f"    ❌ Failed to send card")
        return
    
    print(f"\n" + "=" * 70)
    print(f"  📱 Check Feishu and click a button")
    print(f"  URL: {public_url}")
    print(f"  Task ID: {task_id}")
    print("=" * 70)
    print(f"\n[5] Waiting for decision (300s)...")
    
    decision = None
    
    def wait_for_decision():
        nonlocal decision
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            decision = loop.run_until_complete(
                callback_server.wait_for_decision(task_id, timeout=300)
            )
        except asyncio.TimeoutError:
            decision = "timeout"
        finally:
            loop.close()
    
    wait_thread = threading.Thread(target=wait_for_decision)
    wait_thread.start()
    wait_thread.join()
    
    print(f"\n[6] Decision: {decision}")
    
    if decision == "approve":
        print(f"\n[7] Executing with OpenCode...")
        
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
        
        result = executor.execute(
            "Create a Python calculator with add, subtract, multiply, divide",
            task_id=task_id,
        )
        
        print(f"\n[8] Result:")
        print(f"    Success:  {result.success}")
        print(f"    Duration: {result.duration:.2f}s")
        if result.files_created:
            print(f"    Files:    {result.files_created}")
            
    elif decision == "reject":
        print(f"\n[7] Task rejected.")
    elif decision == "timeout":
        print(f"\n[7] Timeout")
    
    print("\n" + "=" * 70)
    print("  Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
