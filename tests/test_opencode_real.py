"""
测试 OpenCode 实际执行任务

使用方法:
python tests/test_opencode_real.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import subprocess
import time


def test_opencode_simple_task():
    """测试 OpenCode 执行简单任务"""
    print("\n" + "=" * 60)
    print("OpenCode 实际执行测试")
    print("=" * 60)
    
    work_dir = "/mnt/d/project/task-automation/workspace"
    
    print(f"\n工作目录: {work_dir}")
    
    print("\n[步骤 1] 创建工作目录...")
    subprocess.run(
        ["wsl", "mkdir", "-p", work_dir],
        capture_output=True,
        timeout=10,
    )
    print("  [OK] 目录已创建")
    
    print("\n[步骤 2] 测试 OpenCode run 命令...")
    
    instruction = "创建一个名为 hello_opencode.py 的文件，内容是打印 Hello from OpenCode!"
    
    cmd = [
        "wsl", "opencode", "run",
        "--dir", work_dir,
        instruction,
    ]
    
    print(f"  命令: {' '.join(cmd)}")
    print("  执行中... (可能需要几分钟)")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            encoding='utf-8',
            errors='ignore',
        )
        
        duration = time.time() - start_time
        
        print(f"\n  执行时间: {duration:.1f} 秒")
        print(f"  返回码: {result.returncode}")
        
        if result.stdout:
            print(f"\n  标准输出:")
            print("-" * 40)
            print(result.stdout[:2000])
            print("-" * 40)
        
        if result.stderr:
            print(f"\n  标准错误:")
            print("-" * 40)
            print(result.stderr[:1000])
            print("-" * 40)
        
        print("\n[步骤 3] 检查生成的文件...")
        check_result = subprocess.run(
            ["wsl", "ls", "-la", work_dir],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='ignore',
        )
        print(f"  目录内容:")
        print(check_result.stdout)
        
        check_file = subprocess.run(
            ["wsl", "cat", f"{work_dir}/hello_opencode.py"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='ignore',
        )
        if check_file.returncode == 0:
            print(f"  文件内容:")
            print("-" * 40)
            print(check_file.stdout)
            print("-" * 40)
            print("  [OK] 文件创建成功!")
        else:
            print("  [WARN] 文件未创建")
        
    except subprocess.TimeoutExpired:
        print("  [FAIL] 执行超时 (5分钟)")
    except Exception as e:
        print(f"  [FAIL] 执行失败: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_opencode_simple_task()
