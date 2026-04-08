"""
测试 OpenHands 执行器

使用方法:
python tests/test_openhands.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.executor import (
    CodeExecutor,
    ExecutorConfig,
    OpenHandsExecutor,
    ExecutionStatus,
)


def test_openhands_config():
    """测试 OpenHands 配置"""
    print("\n" + "=" * 60)
    print("OpenHands 执行器测试")
    print("=" * 60)
    
    config = ExecutorConfig(
        backend="openhands",
        mode="webui",
        web_url=os.getenv("EXECUTOR_WEB_URL", "http://localhost:3000"),
    )
    
    print(f"\n配置:")
    print(f"  backend: {config.backend}")
    print(f"  mode: {config.mode}")
    print(f"  web_url: {config.web_url}")
    
    executor = OpenHandsExecutor(config)
    
    print(f"\n执行器信息:")
    print(f"  名称: {executor.name}")
    print(f"  支持的模式: {executor.supported_modes}")
    print(f"  当前模式: {config.mode}")
    
    print("\n[测试 1] Dry Run...")
    result = executor.execute(
        instruction="创建一个 hello.py 文件，打印 Hello World",
        task_id="test_openhands_001",
        dry_run=True,
    )
    print(f"  状态: {result.status}")
    print(f"  输出: {result.stdout}")
    
    print("\n[测试 2] 安全检查 - 危险命令...")
    try:
        executor._check_security("rm -rf /")
        print("  [FAIL] 应该被拦截")
    except Exception as e:
        print(f"  [OK] 正确拦截: {e}")
    
    print("\n[测试 3] 安全检查 - 合法命令...")
    try:
        executor._check_security("创建一个合法文件")
        print("  [OK] 合法命令通过")
    except Exception as e:
        print(f"  [FAIL] 不应该被拦截: {e}")
    
    print("\n[测试 4] WebUI 模式...")
    web_url = executor.get_web_url()
    if web_url:
        print(f"  Web URL: {web_url}")
    else:
        print("  Web URL 未配置")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_openhands_config()
