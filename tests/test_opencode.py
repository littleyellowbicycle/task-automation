"""
测试 OpenCode 执行器

使用方法:
python tests/test_opencode.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import subprocess


def test_wsl_connection():
    """测试 WSL 连接"""
    print("\n" + "=" * 60)
    print("WSL 连接测试")
    print("=" * 60)
    
    print("\n[测试 1] 检查 WSL 是否可用...")
    try:
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='ignore',
        )
        print(f"  状态码: {result.returncode}")
        if result.returncode == 0:
            print(f"  [OK] WSL 可用")
        else:
            print(f"  [WARN] WSL 状态异常")
    except FileNotFoundError:
        print("  [FAIL] WSL 未安装")
        return False
    except Exception as e:
        print(f"  [FAIL] 检查失败: {e}")
        return False
    
    print("\n[测试 2] 检查 OpenCode 是否安装...")
    try:
        result = subprocess.run(
            ["wsl", "which", "opencode"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='ignore',
        )
        if result.returncode == 0:
            opencode_path = result.stdout.strip()
            print(f"  [OK] OpenCode 路径: {opencode_path}")
        else:
            print("  [FAIL] OpenCode 未安装")
            print("  请在 WSL 中运行: curl -fsSL https://opencode.ai/install | bash")
            return False
    except Exception as e:
        print(f"  [FAIL] 检查失败: {e}")
        return False
    
    print("\n[测试 3] 检查 OpenCode 版本...")
    try:
        result = subprocess.run(
            ["wsl", "opencode", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='ignore',
        )
        output = result.stdout.strip() or result.stderr.strip()
        print(f"  输出: {output}")
        if result.returncode == 0 or "opencode" in output.lower():
            print("  [OK] OpenCode 可执行")
        else:
            print("  [WARN] 版本检查返回非零状态码")
    except Exception as e:
        print(f"  [FAIL] 检查失败: {e}")
    
    print("\n[测试 4] 测试简单命令...")
    try:
        result = subprocess.run(
            ["wsl", "opencode", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore',
        )
        help_text = result.stdout + result.stderr
        print(f"  帮助信息前 500 字符:")
        print("-" * 40)
        print(help_text[:500])
        print("-" * 40)
        print("  [OK] 命令执行成功")
    except Exception as e:
        print(f"  [FAIL] 命令执行失败: {e}")
    
    print("\n" + "=" * 60)
    return True


def test_executor():
    """测试 CodeExecutor"""
    print("\n" + "=" * 60)
    print("CodeExecutor 测试")
    print("=" * 60)
    
    from src.executor import CodeExecutor, ExecutorConfig
    
    config = ExecutorConfig.from_env()
    print(f"\n配置:")
    print(f"  mode: {config.mode}")
    print(f"  wsl_path: {config.wsl_path}")
    print(f"  api_url: {config.api_url}")
    print(f"  timeout: {config.timeout}")
    
    executor = CodeExecutor(config)
    
    print("\n[测试] 安全检查...")
    try:
        executor._check_security("创建一个 hello.py 文件")
        print("  [OK] 安全检查通过")
    except Exception as e:
        print(f"  [FAIL] 安全检查失败: {e}")
    
    print("\n[测试] 危险命令检测...")
    try:
        executor._check_security("rm -rf /")
        print("  [FAIL] 应该检测到危险命令")
    except Exception as e:
        print(f"  [OK] 正确检测到危险命令: {e}")
    
    print("\n[测试] Dry Run 模式...")
    result = executor.execute(
        instruction="创建一个测试文件",
        task_id="test_dry_run",
        dry_run=True,
    )
    print(f"  状态: {result.status}")
    print(f"  输出: {result.stdout}")
    
    print("\n" + "=" * 60)
    return True


if __name__ == "__main__":
    test_wsl_connection()
    test_executor()
