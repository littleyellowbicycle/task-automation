"""
Test OpenCode executor with SDK mode.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.executor import create_executor, ExecutorConfig

def main():
    config = ExecutorConfig(
        backend="opencode",
        mode="api",
        api_url="http://localhost:4096",
        work_dir="./workspace",
        model_provider="opencode",
        model_id="minimax-m2.5-free",
        timeout=300,
    )
    
    print("Creating OpenCode executor with SDK mode...")
    print(f"Config: backend={config.backend}, mode={config.mode}, model={config.model_provider}/{config.model_id}")
    
    executor = create_executor(config)
    
    print(f"\nExecutor name: {executor.name}")
    print(f"Supported modes: {executor.supported_modes}")
    
    print("\nChecking health...")
    healthy = executor.health_check()
    print(f"Health check: {healthy}")
    
    print("\nExecuting test task...")
    result = executor.execute(
        instruction="Create a file named python_test.txt with content 'Python SDK Test Success'",
        task_id="test_python_sdk_001",
        dry_run=False,
    )
    
    print(f"\nResult:")
    print(f"  Success: {result.success}")
    print(f"  Status: {result.status}")
    print(f"  Duration: {result.duration:.2f}s")
    print(f"  Files created: {result.files_created}")
    print(f"  Files modified: {result.files_modified}")
    if result.error_message:
        print(f"  Error: {result.error_message}")
    print(f"  Metadata: {result.metadata}")

if __name__ == "__main__":
    main()
