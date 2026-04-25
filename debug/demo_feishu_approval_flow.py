"""
Demo script: Simulate task flow with Feishu card approval and OpenCode execution.

Flow:
1. Create a sample task
2. Send approval card to Feishu user
3. Start callback server to receive card click events
4. User clicks confirm on Feishu
5. OpenCode executes the task locally

Usage:
    python demo_feishu_approval_flow.py

Requirements:
    - OpenCode server running (or will auto-start)
    - Feishu app configured with valid credentials
    - Ngrok or similar to expose callback server to internet
"""

import asyncio
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from src.feishu_recorder.client import FeishuClient
from src.feishu_recorder.models import TaskRecord, TaskStatus
from src.callback_server import CallbackServer
from src.code_executor import CodeExecutor

load_dotenv()


class DemoApprovalFlow:
    def __init__(self):
        self.feishu_client = FeishuClient(
            app_id=os.getenv("FEISHU_APP_ID"),
            app_secret=os.getenv("FEISHU_APP_SECRET"),
        )
        self.user_id = os.getenv("FEISHU_USER_ID")
        self.callback_server = CallbackServer(
            host="0.0.0.0",
            port=int(os.getenv("CALLBACK_PORT", "8086")),
            callback_path="/feishu/callback",
            decision_path="/decision",
        )
        self.code_executor = CodeExecutor(
            api_url=os.getenv("OPENCODE_API_URL", "http://localhost:4096"),
            work_dir=os.getenv("OPENCODE_WORK_DIR", "./workspace"),
            timeout=int(os.getenv("OPENCODE_TIMEOUT", "600")),
            model_provider=os.getenv("EXECUTOR_MODEL_PROVIDER", "opencode"),
            model_id=os.getenv("EXECUTOR_MODEL_ID", "minimax-m2.5-free"),
        )
        self.current_task_id = None
        self.pending_tasks = {}

    def _generate_task_id(self, message: str) -> str:
        unique_str = f"{message}_{datetime.now().isoformat()}"
        return f"task_{hashlib.md5(unique_str.encode()).hexdigest()[:8]}"

    def create_sample_task(self, message: str) -> TaskRecord:
        task_id = self._generate_task_id(message)
        self.current_task_id = task_id

        record = TaskRecord(
            task_id=task_id,
            raw_message=message,
            summary=f"创建{message[:20]}...",
            tech_stack=["Python"],
            core_features=["基础功能"],
            status=TaskStatus.PENDING,
            user_id=os.getenv("FEISHU_USER_ID", "unknown"),
            user_name="Demo User",
            created_at=datetime.now(timezone.utc),
        )
        self.pending_tasks[task_id] = {
            "record": record,
            "instruction": message,
        }
        return record

    async def _on_task_approved(self, task_id: str):
        print(f"\n{'=' * 60}")
        print(f"[APPROVED] Task APPROVED: {task_id}")
        print(f"{'=' * 60}")

        if task_id not in self.pending_tasks:
            print(f"Task {task_id} not found in pending tasks!")
            return

        task_info = self.pending_tasks[task_id]
        instruction = task_info["instruction"]

        print(f"\nExecuting via OpenCode...")
        print(f"Instruction: {instruction}")
        print(f"\n{'=' * 60}")

        result = await self.code_executor.execute(instruction, dry_run=False)

        print(f"\n{'=' * 60}")
        print("EXECUTION RESULT")
        print(f"{'=' * 60}")
        print(f"Success: {result.success}")
        print(f"Duration: {result.duration:.2f}s")
        print(f"Exit Code: {result.exit_code}")
        if result.stdout:
            print(f"\nOutput:\n{result.stdout[:500]}...")
        if result.stderr:
            print(f"\nErrors:\n{result.stderr[:500]}...")
        if result.repo_url:
            print(f"\nRepo URL: {result.repo_url}")
        print(f"{'=' * 60}")

        del self.pending_tasks[task_id]

    async def _on_task_rejected(self, task_id: str):
        print(f"\n{'=' * 60}")
        print(f"[REJECTED] Task REJECTED: {task_id}")
        print(f"{'=' * 60}")
        if task_id in self.pending_tasks:
            del self.pending_tasks[task_id]

    async def _on_task_later(self, task_id: str):
        print(f"\n{'=' * 60}")
        print(f"[DEFERRED] Task DEFERRED: {task_id}")
        print(f"{'=' * 60}")

    async def _setup_callbacks(self):
        self.callback_server.on_approved(self._on_task_approved)
        self.callback_server.on_rejected(self._on_task_rejected)
        self.callback_server.on_later(self._on_task_later)

    async def send_approval_card(self, task_record: TaskRecord) -> bool:
        callback_url = f"http://localhost:{self.callback_server.port}"
        card = self.feishu_client.create_task_card(task_record, callback_url)

        user_id = self.user_id
        if not user_id:
            print("ERROR: FEISHU_USER_ID not set in environment")
            return False

        print(f"Sending approval card to user: {user_id}")
        print(f"Callback URL: {callback_url}")
        print(f"\nCard Preview:")
        print(f"  Title: 任务审批: {task_record.task_id}")
        print(f"  Summary: {task_record.summary}")
        print(f"  Tech Stack: {', '.join(task_record.tech_stack)}")

        message_id = self.feishu_client.send_private_message(
            user_id=user_id,
            content=card,
            msg_type="interactive",
        )

        if message_id:
            print(f"\n[OK] Card sent successfully! Message ID: {message_id}")
            return True
        else:
            print("\n[FAIL] Failed to send card")
            return False

    async def run(self, task_instruction: str):
        print(f"\n{'=' * 60}")
        print("Feishu Task Approval Demo")
        print(f"{'=' * 60}")

        task_record = self.create_sample_task(task_instruction)
        print(f"\nCreated Task:")
        print(f"  Task ID: {task_record.task_id}")
        print(f"  Message: {task_record.raw_message}")

        await self._setup_callbacks()

        print(f"\nStarting callback server on port {self.callback_server.port}...")

        import threading

        server_ready = threading.Event()

        def run_server():
            import uvicorn

            server_ready.set()
            uvicorn.run(
                self.callback_server.app,
                host="0.0.0.0",
                port=self.callback_server.port,
                log_level="warning",
            )

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        server_ready.wait()

        print(f"Callback server started!")
        print(f"\nSend the approval card to Feishu...")

        card_sent = await self.send_approval_card(task_record)
        if not card_sent:
            print("Failed to send card, exiting...")
            return

        print(f"\n{'=' * 60}")
        print("WAITING FOR USER APPROVAL")
        print(f"{'=' * 60}")
        print(f"\nPlease click on the Feishu card to approve or reject.")
        print(f"Waiting for decision on task: {task_record.task_id}")
        print(f"\nCallback URL: http://localhost:{self.callback_server.port}/decision")
        print(f"\nThe buttons will call:")
        print(
            f"  - http://localhost:{self.callback_server.port}/decision?task_id={task_record.task_id}&action=approve"
        )
        print(
            f"  - http://localhost:{self.callback_server.port}/decision?task_id={task_record.task_id}&action=reject"
        )
        print(
            f"  - http://localhost:{self.callback_server.port}/decision?task_id={task_record.task_id}&action=later"
        )

        print(
            f"\n[WARNING] NOTE: For Feishu to call this server, you need to expose it via ngrok:"
        )
        print(f"   ngrok http {self.callback_server.port}")
        print(f"\n   Then update your Feishu app's request URL to use the ngrok URL.")

        try:
            while task_record.task_id in self.pending_tasks:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nDemo interrupted by user")
            return


async def main():
    default_task = "创建一个 Python 脚本，计算两个数的和并输出结果"

    if len(sys.argv) > 1:
        task_instruction = " ".join(sys.argv[1:])
    else:
        task_instruction = default_task
        print(f"No task specified, using default: {task_instruction}")

    demo = DemoApprovalFlow()
    await demo.run(task_instruction)


if __name__ == "__main__":
    asyncio.run(main())
