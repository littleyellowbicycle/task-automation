"""
Test the complete workflow: Callback -> Executor.
Run this script, then open the approve URL in your browser.
"""
import sys
import os
import threading
import time
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.callback_server import CallbackServer
from src.executor import create_executor, ExecutorConfig
import uvicorn
import requests


def run_callback_server(callback_server, port):
    """Run callback server in a thread."""
    uvicorn.run(callback_server.app, host="0.0.0.0", port=port, log_level="warning")


def main():
    print("=" * 70)
    print("  Complete Workflow Test: Callback -> OpenCode Executor")
    print("=" * 70)
    
    port = 8084
    callback_server = CallbackServer(host="0.0.0.0", port=port)
    
    print(f"\n[1/5] Starting callback server on port {port}...")
    server_thread = threading.Thread(
        target=run_callback_server, 
        args=(callback_server, port),
        daemon=True
    )
    server_thread.start()
    time.sleep(3)
    print(f"      ✅ Callback server running")
    
    task_id = "workflow_test_001"
    
    print(f"\n[2/5] Task ready for approval")
    print(f"      Task ID: {task_id}")
    print(f"      Task: Create a Python hello world script")
    
    approve_url = f"http://localhost:{port}/decision?task_id={task_id}&action=approve"
    reject_url = f"http://localhost:{port}/decision?task_id={task_id}&action=reject"
    
    print(f"\n[3/5] 🔗 Open this URL in your browser to APPROVE:")
    print(f"      {approve_url}")
    print(f"\n      Or REJECT:")
    print(f"      {reject_url}")
    
    print(f"\n[4/5] Waiting for your decision...")
    print(f"      (Simulating approval in 5 seconds for testing...)")
    
    time.sleep(5)
    
    print(f"\n      Simulating approval by calling the callback URL...")
    try:
        response = requests.get(approve_url, timeout=10)
        print(f"      Response: {response.status_code}")
        print(f"      Body: {response.text[:200]}")
    except Exception as e:
        print(f"      Error calling callback: {e}")
    
    time.sleep(2)
    
    print(f"\n[5/5] Checking decision...")
    decision = callback_server.get_decision(task_id)
    print(f"      Decision: {decision}")
    
    if decision == "approve":
        print(f"\n      ✅ Task approved! Executing with OpenCode...")
        
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
        
        print("      Sending task to OpenCode (MiniMax M2.5 Free)...")
        
        import asyncio
        result = asyncio.run(executor.execute_async(
            "Create a Python script named hello_workflow.py that prints 'Hello from Workflow Test!'",
            task_id=task_id,
        ))
        
        print(f"\n      {'=' * 50}")
        print(f"      Execution Result:")
        print(f"      {'=' * 50}")
        print(f"      Success:  {result.success}")
        print(f"      Status:   {result.status}")
        print(f"      Duration: {result.duration:.2f}s")
        if result.files_created:
            print(f"      Files:    {result.files_created}")
        if result.error_message:
            print(f"      Error:    {result.error_message}")
        if result.stdout:
            print(f"      Output:   {result.stdout[:200]}")
            
    elif decision == "reject":
        print(f"\n      ❌ Task rejected. Workflow cancelled.")
        
    else:
        print(f"\n      ⚠️ No decision received: {decision}")
    
    print("\n" + "=" * 70)
    print("  Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
