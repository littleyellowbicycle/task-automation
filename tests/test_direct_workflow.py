"""
Direct test: Callback -> Executor without complex async.
"""
import sys
import os
import time
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import uvicorn
from src.callback_server import CallbackServer
from src.executor import create_executor, ExecutorConfig


def run_server(app, port):
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def main():
    print("=" * 70)
    print("  Direct Test: Callback -> OpenCode Executor")
    print("=" * 70)
    
    port = 8085
    callback_server = CallbackServer(host="0.0.0.0", port=port)
    
    print(f"\n[1] Starting callback server on port {port}...")
    thread = threading.Thread(
        target=run_server,
        args=(callback_server.app, port),
        daemon=True
    )
    thread.start()
    time.sleep(2)
    print("    ✅ Server started")
    
    task_id = "direct_test_001"
    
    print(f"\n[2] Testing callback...")
    approve_url = f"http://localhost:{port}/decision?task_id={task_id}&action=approve"
    
    try:
        resp = requests.get(approve_url, timeout=5)
        print(f"    Response: {resp.status_code}")
        print(f"    Body: {resp.json()}")
    except Exception as e:
        print(f"    Error: {e}")
        return
    
    print(f"\n[3] Checking decision...")
    decision = callback_server.get_decision(task_id)
    print(f"    Decision: {decision}")
    
    if decision == "approve":
        print(f"\n[4] Executing with OpenCode...")
        
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
            "Create a file named direct_test.txt with content 'Direct Test Success!'",
            task_id=task_id,
        )
        
        print(f"\n[5] Result:")
        print(f"    Success:  {result.success}")
        print(f"    Status:   {result.status}")
        print(f"    Duration: {result.duration:.2f}s")
        if result.files_created:
            print(f"    Files:    {result.files_created}")
        if result.error_message:
            print(f"    Error:    {result.error_message}")
    else:
        print(f"\n[4] Decision not received: {decision}")
    
    print("\n" + "=" * 70)
    print("  Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
