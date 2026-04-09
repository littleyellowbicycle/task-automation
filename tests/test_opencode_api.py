"""
测试 OpenCode SDK 桥接

使用方法:
python tests/test_opencode_api.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.executor import ExecutorConfig, ExecutionStatus
from src.executor.opencode import OpenCodeExecutor


def test_sdk_bridge():
    """测试 OpenCode SDK 桥接"""
    print("\n" + "=" * 60)
    print("OpenCode SDK 桥接测试")
    print("=" * 60)
    
    config = ExecutorConfig(
        backend="opencode",
        mode="api",
        api_url=os.getenv("EXECUTOR_WEB_URL", "http://localhost:4096"),
        work_dir="./workspace",
        timeout=120,
    )
    
    print(f"\n配置:")
    print(f"  backend: {config.backend}")
    print(f"  mode: {config.mode}")
    print(f"  api_url: {config.api_url}")
    
    executor = OpenCodeExecutor(config)
    
    print("\n[测试 1] Dry Run...")
    result = executor.execute(
        instruction="创建一个 hello.py 文件",
        task_id="test_sdk_001",
        dry_run=True,
    )
    print(f"  状态: {result.status}")
    print(f"  输出: {result.stdout}")
    
    print("\n[测试 2] 实际执行...")
    print("  执行中... (可能需要几分钟)")
    
    result = executor.execute(
        instruction="在当前目录创建一个名为 test_sdk_hello.py 的文件，内容是 print('Hello from OpenCode SDK!')",
        task_id="test_sdk_real_001",
    )
    
    print(f"\n  执行结果:")
    print(f"    状态: {result.status}")
    print(f"    成功: {result.success}")
    print(f"    耗时: {result.duration:.1f}s")
    
    if result.stdout:
        print(f"    输出: {result.stdout[:200]}")
    if result.stderr:
        print(f"    错误: {result.stderr[:200]}")
    if result.files_created:
        print(f"    创建的文件: {result.files_created}")
    if result.error_message:
        print(f"    错误信息: {result.error_message}")


if __name__ == "__main__":
    test_sdk_bridge()
