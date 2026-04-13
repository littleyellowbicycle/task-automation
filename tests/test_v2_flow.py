"""
End-to-end test for v2 architecture (standalone mode).

Tests the full flow: message -> filter -> analysis -> decision -> execution -> recording
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import threading
import asyncio
from dotenv import load_dotenv

load_dotenv()

import uvicorn
import httpx


def main():
    print("=" * 70)
    print("  V2 Architecture End-to-End Test")
    print("=" * 70)

    from src.gateway import create_gateway_app, InProcessDispatcher
    from src.workers.filter_analysis.handler import FilterAnalysisHandler
    from src.workers.decision.handler import DecisionHandler
    from src.workers.execution.handler import ExecutionHandler
    from src.workers.recording.handler import RecordingHandler

    PORT = 8088
    BASE_URL = f"http://localhost:{PORT}"

    dispatcher = InProcessDispatcher()

    handler_analysis = FilterAnalysisHandler()
    handler_decision = DecisionHandler(
        gateway_url=BASE_URL,
        feishu_app_id=os.getenv("FEISHU_APP_ID", ""),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL", ""),
        feishu_user_id=os.getenv("FEISHU_USER_ID", ""),
    )
    handler_execution = ExecutionHandler(
        gateway_url=BASE_URL,
        api_url=os.getenv("OPENCODE_API_URL", "http://localhost:4096"),
        work_dir="./workspace",
        timeout=60,
        model_provider=os.getenv("EXECUTOR_MODEL_PROVIDER", "opencode"),
        model_id=os.getenv("EXECUTOR_MODEL_ID", "minimax-m2.5-free"),
    )
    handler_recording = RecordingHandler(
        gateway_url=BASE_URL,
        feishu_app_id=os.getenv("FEISHU_APP_ID", ""),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        feishu_table_id=os.getenv("FEISHU_TABLE_ID", ""),
        feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL", ""),
    )

    task_events = {}

    async def _on_analysis(task_id: str, content: str, msg_id: str = ""):
        print(f"  [ANALYSIS] task_id={task_id}, content={content[:50]}...")
        try:
            result = await handler_analysis.handle_analyze(task_id=task_id, content=content, msg_id=msg_id)
            print(f"  [ANALYSIS] result: is_task={result.get('is_task')}, summary={result.get('summary', '')[:50]}")

            app = _get_app()
            mr = app.state.message_router

            if not result.get("is_task"):
                from src.gateway.models.tasks import TaskStatus
                app.state.task_manager.update_status(task_id, TaskStatus.CANCELLED, error=result.get("reason", "not_task"))
                task_events[task_id] = "cancelled_not_task"
                return

            await mr.route_analysis_done(task_id, result)
        except Exception as e:
            print(f"  [ANALYSIS] ERROR: {e}")
            import traceback
            traceback.print_exc()

    async def _on_decision(task_id: str, task_record: dict, analysis: dict):
        print(f"  [DECISION] task_id={task_id}")
        try:
            result = await handler_decision.handle_decision_request(
                task_id=task_id, task_record=task_record, analysis=analysis
            )
            print(f"  [DECISION] card sent, waiting for user action...")
        except Exception as e:
            print(f"  [DECISION] ERROR: {e}")
            import traceback
            traceback.print_exc()

    async def _on_decision_callback(task_id: str, action: str):
        print(f"  [DECISION CALLBACK] task_id={task_id}, action={action}")
        try:
            result = await handler_decision.handle_decision_callback(task_id=task_id, action=action)
            app = _get_app()
            mr = app.state.message_router
            await mr.route_decision(task_id, action)
            task_events[task_id] = f"decision_{action}"
        except Exception as e:
            print(f"  [DECISION CALLBACK] ERROR: {e}")
            import traceback
            traceback.print_exc()

    async def _on_execution(task_id: str, summary: str, raw_message: str = ""):
        print(f"  [EXECUTION] task_id={task_id}, summary={summary[:50]}...")
        try:
            result = await handler_execution.handle_execution_request(
                task_id=task_id, summary=summary, raw_message=raw_message
            )
            print(f"  [EXECUTION] result: success={result.get('success')}")
        except Exception as e:
            print(f"  [EXECUTION] ERROR: {e}")
            import traceback
            traceback.print_exc()

    async def _on_recording(task_id: str, task_record: dict, success: bool, message: str = ""):
        print(f"  [RECORDING] task_id={task_id}, success={success}")
        try:
            result = await handler_recording.handle_recording_request(
                task_id=task_id, task_record=task_record, success=success, message=message
            )
            task_events[task_id] = "completed" if success else "failed"
            print(f"  [RECORDING] done")
        except Exception as e:
            print(f"  [RECORDING] ERROR: {e}")
            import traceback
            traceback.print_exc()

    dispatcher.set_analysis_handler(_on_analysis)
    dispatcher.set_decision_handler(_on_decision)
    dispatcher.set_decision_callback_handler(_on_decision_callback)
    dispatcher.set_execution_handler(_on_execution)
    dispatcher.set_recording_handler(_on_recording)

    app = create_gateway_app(
        mode="standalone",
        dedup_enabled=False,
        dispatcher=dispatcher,
    )

    _app_ref = [app]

    def _get_app():
        return _app_ref[0]

    print(f"\n[1] Starting gateway on port {PORT}...")

    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning"),
        daemon=True,
    )
    server_thread.start()
    time.sleep(3)
    print("    Gateway started")

    print(f"\n[2] Checking health...")
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        data = r.json()
        print(f"    Status: {data.get('status')}")
        print(f"    Queue size: {data.get('components', {}).get('queue', {}).get('size')}")
    except Exception as e:
        print(f"    Health check failed: {e}")
        return

    print(f"\n[3] Sending test message...")
    message = {
        "content": "项目发布：开发一个用户登录功能，使用 Python Flask 框架",
        "sender_id": "user_001",
        "sender_name": "Test User",
        "conversation_id": "R:group_001",
        "conversation_type": "group",
        "msg_id": f"e2e_test_{int(time.time())}",
        "msg_type": "text",
        "platform": "wework",
        "listener_type": "ocr",
    }

    try:
        r = httpx.post(f"{BASE_URL}/api/v1/listener/msg", json=message, timeout=10.0)
        result = r.json()
        task_id = result.get("task_id")
        print(f"    Response: code={result.get('code')}, task_id={task_id}")
    except Exception as e:
        print(f"    Failed: {e}")
        return

    if not task_id:
        print("    No task_id returned, aborting")
        return

    time.sleep(2)

    print(f"\n[4] Checking task status after analysis...")
    try:
        r = httpx.get(f"{BASE_URL}/api/v1/tasks/{task_id}", timeout=5.0)
        task_data = r.json()
        status = task_data.get("data", {}).get("status", task_data.get("status"))
        print(f"    Task status: {status}")
    except Exception as e:
        print(f"    Failed to get task status: {e}")

    print(f"\n[5] Testing decision callback (simulating Feishu approve)...")
    callback_data = {
        "event": {
            "type": "card.action.trigger",
            "action": {
                "value": {"task_id": task_id, "action": "approve"},
            },
        }
    }
    try:
        r = httpx.post(f"{BASE_URL}/api/v1/feishu/callback", json=callback_data, timeout=10.0)
        print(f"    Callback response: {r.json()}")
    except Exception as e:
        print(f"    Callback failed: {e}")

    time.sleep(5)

    print(f"\n[6] Final task status...")
    try:
        r = httpx.get(f"{BASE_URL}/api/v1/tasks/{task_id}", timeout=5.0)
        task_data = r.json()
        status = task_data.get("data", {}).get("status", task_data.get("status"))
        print(f"    Task status: {status}")
    except Exception as e:
        print(f"    Failed: {e}")

    print(f"\n[7] Task events: {task_events}")

    print("\n" + "=" * 70)
    print("  Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
