"""
Test the complete workflow: Feishu card -> User confirmation -> OpenCode execution.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.workflow_orchestrator import WorkflowOrchestrator
from src.feishu_recorder.models import TaskRecord, TaskStatus
from datetime import datetime, timezone


async def test_complete_workflow():
    print("=" * 60)
    print("Testing Complete Workflow: Feishu Card -> Confirmation -> Execution")
    print("=" * 60)
    
    orchestrator = WorkflowOrchestrator(
        callback_host="0.0.0.0",
        callback_port=8080,
        dry_run=False,
    )
    
    print("\n1. Starting callback server...")
    orchestrator.start_callback_server()
    
    await asyncio.sleep(2)
    
    print(f"\n2. Callback URL: {orchestrator.get_callback_url()}")
    
    print("\n3. Creating test task record...")
    task_record = TaskRecord(
        task_id="test_workflow_001",
        raw_message="创建一个Python脚本，实现简单的计算器功能，包括加减乘除",
        summary="创建Python计算器脚本",
        tech_stack=["Python"],
        core_features=["add", "subtract", "multiply", "divide"],
        status=TaskStatus.PENDING,
        user_id="test_user",
        user_name="Test User",
        created_at=datetime.now(timezone.utc),
    )
    
    print(f"   Task ID: {task_record.task_id}")
    print(f"   Summary: {task_record.summary}")
    print(f"   Tech Stack: {task_record.tech_stack}")
    
    print("\n4. Sending approval card to Feishu...")
    callback_url = orchestrator.get_callback_url()
    success = orchestrator.feishu_bridge.send_approval_card(task_record, callback_url=callback_url)
    
    if success:
        print("   ✅ Approval card sent successfully!")
        print(f"   📱 Check your Feishu for the approval card")
        print(f"   🔗 Or manually approve via: {callback_url}/decision?task_id={task_record.task_id}&action=approve")
    else:
        print("   ❌ Failed to send approval card")
        print("   (This is expected if Feishu credentials are not configured)")
    
    print("\n5. Waiting for user decision...")
    print("   Click the button in Feishu card or use the URL above")
    print("   Waiting up to 60 seconds for decision...")
    
    try:
        decision_action = await asyncio.wait_for(
            orchestrator.callback_server.wait_for_decision(task_record.task_id),
            timeout=60
        )
        
        print(f"\n6. Decision received: {decision_action}")
        
        if decision_action == "approve":
            print("\n7. Task approved! Executing via OpenCode...")
            
            instruction = f"创建代码: {task_record.summary}"
            print(f"   Instruction: {instruction}")
            
            result = await orchestrator.code_executor.execute(
                instruction, 
                dry_run=False
            )
            
            print(f"\n8. Execution result:")
            print(f"   Success: {result.success}")
            print(f"   Status: {result.status}")
            print(f"   Duration: {result.duration:.2f}s")
            if result.files_created:
                print(f"   Files created: {result.files_created}")
            if result.error_message:
                print(f"   Error: {result.error_message}")
            if result.stdout:
                print(f"   Output: {result.stdout[:500]}")
                
        elif decision_action == "reject":
            print("\n7. Task rejected. Cancelling...")
            
        elif decision_action == "later":
            print("\n7. Task deferred. Will be requeued...")
            
        else:
            print(f"\n7. Unknown decision: {decision_action}")
            
    except asyncio.TimeoutError:
        print("\n⏱️ Decision timeout (60 seconds)")
        print("   Task was not confirmed within the timeout period")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


async def test_manual_approval():
    """Test with manual approval via HTTP request."""
    print("=" * 60)
    print("Testing Manual Approval Flow")
    print("=" * 60)
    
    orchestrator = WorkflowOrchestrator(
        callback_host="0.0.0.0",
        callback_port=8080,
        dry_run=False,
    )
    
    print("\n1. Starting callback server...")
    orchestrator.start_callback_server()
    
    await asyncio.sleep(2)
    
    task_id = "test_manual_001"
    
    print(f"\n2. Simulating task pending approval...")
    print(f"   Task ID: {task_id}")
    
    callback_url = orchestrator.get_callback_url()
    approve_url = f"{callback_url}/decision?task_id={task_id}&action=approve"
    
    print(f"\n3. To approve, open this URL in your browser:")
    print(f"   {approve_url}")
    
    print("\n4. Or use curl:")
    print(f'   curl "{approve_url}"')
    
    print("\n5. Waiting for approval (60 seconds)...")
    
    try:
        decision = await asyncio.wait_for(
            orchestrator.callback_server.wait_for_decision(task_id),
            timeout=60
        )
        
        print(f"\n6. Decision received: {decision}")
        
        if decision == "approve":
            print("\n7. Executing task with OpenCode...")
            result = await orchestrator.code_executor.execute(
                "Create a simple hello.py file that prints Hello World",
                dry_run=False
            )
            print(f"   Success: {result.success}")
            print(f"   Duration: {result.duration:.2f}s")
            
    except asyncio.TimeoutError:
        print("\n⏱️ Timeout waiting for approval")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test workflow")
    parser.add_argument("--manual", action="store_true", help="Test manual approval")
    args = parser.parse_args()
    
    if args.manual:
        asyncio.run(test_manual_approval())
    else:
        asyncio.run(test_complete_workflow())
