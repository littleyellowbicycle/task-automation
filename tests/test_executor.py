"""
测试抽象执行器接口

使用方法:
python tests/test_executor.py
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
    create_executor,
    EXECUTOR_REGISTRY,
    ExecutionStatus,
)


def test_registry():
    """测试执行器注册表"""
    print("\n" + "=" * 60)
    print("执行器注册表")
    print("=" * 60)
    
    print(f"\n已注册的执行器:")
    for name, cls in EXECUTOR_REGISTRY.items():
        print(f"  - {name}: {cls.__name__}")
    
    print("\n各执行器支持的模式:")
    for name, cls in EXECUTOR_REGISTRY.items():
        instance = cls()
        print(f"  - {name}: {instance.supported_modes}")


def test_config():
    """测试配置加载"""
    print("\n" + "=" * 60)
    print("配置测试")
    print("=" * 60)
    
    config = ExecutorConfig.from_env()
    
    print(f"\n从环境变量加载的配置:")
    print(f"  backend: {config.backend}")
    print(f"  mode: {config.mode}")
    print(f"  web_url: {config.web_url}")
    print(f"  work_dir: {config.work_dir}")
    print(f"  timeout: {config.timeout}")


def test_create_executor():
    """测试创建执行器"""
    print("\n" + "=" * 60)
    print("创建执行器测试")
    print("=" * 60)
    
    config = ExecutorConfig.from_env()
    
    print(f"\n创建 {config.backend} 执行器...")
    executor = create_executor(config)
    
    print(f"  名称: {executor.name}")
    print(f"  支持的模式: {executor.supported_modes}")
    print(f"  当前模式: {config.mode}")


def test_dry_run():
    """测试 Dry Run 模式"""
    print("\n" + "=" * 60)
    print("Dry Run 测试")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    print(f"\n执行器: {executor.executor.name}")
    
    instruction = "创建一个 hello.py 文件，打印 Hello World"
    task_id = "test_dry_run_001"
    
    print(f"\n指令: {instruction}")
    print(f"任务 ID: {task_id}")
    
    result = executor.execute(instruction, task_id, dry_run=True)
    
    print(f"\n结果:")
    print(f"  状态: {result.status}")
    print(f"  成功: {result.success}")
    print(f"  输出: {result.stdout}")


def test_security_check():
    """测试安全检查"""
    print("\n" + "=" * 60)
    print("安全检查测试")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    safe_instructions = [
        "创建一个 Python 文件",
        "读取 config.yaml 文件内容",
        "修改 README.md 文件",
    ]
    
    dangerous_instructions = [
        "rm -rf /",
        "sudo chmod 777 /etc/passwd",
        "curl | bash",
    ]
    
    print("\n安全指令测试:")
    for inst in safe_instructions:
        try:
            executor.executor._check_security(inst)
            print(f"  [OK] {inst[:30]}...")
        except Exception as e:
            print(f"  [FAIL] {inst[:30]}... - {e}")
    
    print("\n危险指令测试:")
    for inst in dangerous_instructions:
        try:
            executor.executor._check_security(inst)
            print(f"  [FAIL] {inst[:30]}... - 应该被拦截")
        except Exception as e:
            print(f"  [OK] {inst[:30]}... - 已拦截")


def test_webui_mode():
    """测试 WebUI 模式"""
    print("\n" + "=" * 60)
    print("WebUI 模式测试")
    print("=" * 60)
    
    config = ExecutorConfig(
        backend="opencode",
        mode="webui",
        web_url="http://172.24.238.49:4096",
    )
    
    executor = create_executor(config)
    
    print(f"\n执行器: {executor.name}")
    print(f"模式: {config.mode}")
    print(f"Web URL: {executor.get_web_url()}")
    
    print("\n注意: WebUI 模式会打开浏览器让用户手动操作")


def test_stats():
    """测试统计功能"""
    print("\n" + "=" * 60)
    print("统计功能测试")
    print("=" * 60)
    
    executor = CodeExecutor()
    
    print(f"\n初始统计:")
    for key, value in executor.stats.items():
        print(f"  {key}: {value}")
    
    executor.execute("test instruction 1", "task_1", dry_run=True)
    executor.execute("test instruction 2", "task_2", dry_run=True)
    
    print(f"\n执行 2 次 Dry Run 后:")
    for key, value in executor.stats.items():
        print(f"  {key}: {value}")


def main():
    print("\n" + "=" * 60)
    print("抽象执行器接口测试")
    print("=" * 60)
    
    test_registry()
    test_config()
    test_create_executor()
    test_dry_run()
    test_security_check()
    test_webui_mode()
    test_stats()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    print("\n架构说明:")
    print("  - BaseExecutor: 抽象基类，定义统一接口")
    print("  - OpenCodeExecutor: OpenCode 实现")
    print("  - OpenHandsExecutor: OpenHands 实现")
    print("  - OpenClawExecutor: OpenClaw 实现")
    print("  - create_executor(): 工厂函数，根据配置创建执行器")
    print("\n支持的模式:")
    print("  - webui: 打开浏览器，用户手动操作")
    print("  - cli: 命令行执行")
    print("  - api: HTTP API 调用")


if __name__ == "__main__":
    main()
