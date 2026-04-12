"""
Simple test for the complete workflow.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.callback_server import CallbackServer, Decision
from src.executor import create_executor, ExecutorConfig


@pytest.mark.integration
async def test_callback_to_executor():
    print("=" * 60)
    print("Test: Callback -> Executor Integration")
    print("=" * 60)
    
    callback_server = CallbackServer(host="0.0.0.0", port=8082)
    
    print("\n1. Starting callback server...")
    
    import threading
    import uvicorn
    
    def run_server():
        uvicorn.run(callback_server.app, host="0.0.0.0", port=8082, log_level="warning")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    await asyncio.sleep(2)
    print("   ✅ Callback server started on port 8082")
    
    task_id = "test_integration_001"
    
    print(f"\n2. Waiting for decision on task: {task_id}")
    print(f"   Approve URL: http://localhost:8082/decision?task_id={task_id}&action=approve")
    print(f"   Reject URL: http://localhost:8082/decision?task_id={task_id}&action=reject")
    
    print("\n3. Open the approve URL in your browser, or wait for timeout...")
    
    try:
        decision = await asyncio.wait_for(
            callback_server.wait_for_decision(task_id),
            timeout=120
        )
        
        print(f"\n4. Decision received: {decision}")
        
        if decision == Decision.APPROVED.value:
            print("\n5. Task approved! Executing with OpenCode...")
            
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
            
            print("   Sending task to OpenCode...")
            result = await executor.execute_async(
                "Create a file named integration_test.txt with content 'Integration Test Success'",
                task_id=task_id,
            )
            
            print(f"\n6. Execution result:")
            print(f"   Success: {result.success}")
            print(f"   Status: {result.status}")
            print(f"   Duration: {result.duration:.2f}s")
            if result.files_created:
                print(f"   Files created: {result.files_created}")
            if result.error_message:
                print(f"   Error: {result.error_message}")
                
        elif decision == Decision.REJECTED.value:
            print("\n5. Task rejected. Cancelling...")
            
        elif decision == Decision.LATER.value:
            print("\n5. Task deferred...")
            
        else:
            print(f"\n5. Unknown decision: {decision}")
            
    except asyncio.TimeoutError:
        print("\n⏱️ Timeout waiting for decision (120 seconds)")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_callback_to_executor())
