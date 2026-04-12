"""
飞书对接测试脚本

测试内容:
1. 获取 tenant_access_token
2. 发送测试消息到飞书私聊
3. 创建测试记录到飞书多维表格

使用方法:
1. 确保 .env 文件中配置了飞书相关参数
2. 运行: python tests/test_feishu_integration.py
"""

import os
import sys
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.feishu_recorder.client import FeishuClient
from src.feishu_recorder.models import TaskRecord, TaskStatus


def print_separator(title: str = ""):
    print("\n" + "=" * 60)
    if title:
        print(f" {title}")
        print("=" * 60)


def check_get_token(client: FeishuClient):
    """测试获取 tenant_access_token"""
    print_separator("测试 1: 获取 tenant_access_token")
    
    token = client._get_tenant_access_token()
    
    if token:
        print("[OK] 成功获取 token")
        print(f"   Token: {token[:20]}...")
        print(f"   过期时间: {datetime.fromtimestamp(client._token_expires_at)}")
        return True
    else:
        print("[FAIL] 获取 token 失败")
        print("   请检查 FEISHU_APP_ID 和 FEISHU_APP_SECRET 是否正确")
        return False


def check_send_private_message(client: FeishuClient):
    """测试发送私聊消息"""
    print_separator("测试 2: 发送私聊消息")
    
    user_id = os.getenv("FEISHU_USER_ID")
    if not user_id or user_id == "ou_xxxx":
        print("[SKIP] 未配置 FEISHU_USER_ID，跳过此测试")
        return None
    
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "飞书对接测试"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**测试状态**: 连接成功"
                }
            }
        ]
    }
    
    message_id = client.send_private_message(user_id, card)
    
    if message_id:
        print("[OK] 私聊消息发送成功")
        print(f"   Message ID: {message_id}")
        print("   请检查飞书是否收到消息")
        return True
    else:
        print("[FAIL] 私聊消息发送失败")
        return False


def check_create_record(client: FeishuClient):
    """测试创建多维表格记录（测试后自动清理）"""
    print_separator("测试 3: 创建多维表格记录")
    
    if not client.bitable_token or client.bitable_token == "bascnXXXXXXXXXX":
        print("[SKIP] 未配置 FEISHU_BITABLE_TOKEN，跳过此测试")
        return None
    
    if not client.table_id:
        print("[SKIP] 未配置 FEISHU_TABLE_ID，跳过此测试")
        return None
    
    test_task = TaskRecord(
        task_id=f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        raw_message="这是一条测试消息，用于验证飞书多维表格对接",
        summary="飞书对接测试任务",
        tech_stack=["Python", "FastAPI"],
        core_features=["测试功能"],
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
    )
    
    success = client.create_record(test_task)
    
    if success:
        print("[OK] 记录创建成功")
        print(f"   Task ID: {test_task.task_id}")
        
        print("\n   正在清理测试记录...")
        if client.delete_record(test_task.task_id):
            print("[OK] 测试记录已删除")
        else:
            print("[WARN] 测试记录删除失败，请手动清理")
        
        return True
    else:
        print("[FAIL] 记录创建失败")
        print("   请检查 FEISHU_BITABLE_TOKEN 和 FEISHU_TABLE_ID 是否正确")
        print("   请检查多维表格是否有正确的字段")
        return False


def check_task_card(client: FeishuClient):
    """测试发送任务审批卡片"""
    print_separator("测试 4: 发送任务审批卡片")
    
    user_id = os.getenv("FEISHU_USER_ID")
    if not user_id or user_id == "ou_xxxx":
        print("[SKIP] 未配置 FEISHU_USER_ID，跳过此测试")
        return None
    
    test_task = TaskRecord(
        task_id=f"approval_test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        raw_message="开发用户登录功能，支持手机号和邮箱登录",
        summary="开发用户登录功能",
        tech_stack=["Python", "FastAPI", "JWT"],
        core_features=["用户登录", "JWT认证", "密码加密"],
        status=TaskStatus.PENDING,
    )
    
    card = client.create_task_card(test_task)
    message_id = client.send_private_message(user_id, card)
    
    if message_id:
        print("[OK] 任务审批卡片发送成功")
        print(f"   Task ID: {test_task.task_id}")
        print("   请检查飞书是否收到审批卡片")
        return True
    else:
        print("[FAIL] 任务审批卡片发送失败")
        return False


def check_env_config():
    """检查环境变量配置"""
    print_separator("检查环境变量配置")
    
    required_vars = {
        "FEISHU_APP_ID": "飞书应用 ID",
        "FEISHU_APP_SECRET": "飞书应用密钥",
        "FEISHU_BITABLE_TOKEN": "飞书多维表格 Token",
        "FEISHU_TABLE_ID": "飞书多维表格 Table ID",
        "FEISHU_USER_ID": "接收私聊消息的用户 ID",
    }
    
    all_configured = True
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"[OK] {desc}: {masked}")
        else:
            print(f"[MISS] {desc}: 未配置")
            all_configured = False
    
    return all_configured


def main():
    print("\n" + "=" * 60)
    print("        飞书对接测试")
    print("=" * 60)
    
    print("\n📋 正确的任务流程:")
    print("   1. 任务进入队列 (PENDING)")
    print("   2. 发送确认卡片到飞书")
    print("   3. 用户确认 → 创建表格记录 → 开始执行")
    print("   4. 用户取消 → 不创建记录 → 任务移除")
    print("   5. 用户稍后 → 任务放回队列尾部")
    
    env_configured = check_env_config()
    
    if not env_configured:
        print("\n[WARN] 部分环境变量未配置，部分测试将被跳过")
        print("   请在 .env 文件中配置以下变量:")
        print("   - FEISHU_APP_ID")
        print("   - FEISHU_APP_SECRET")
        print("   - FEISHU_BITABLE_TOKEN (多维表格 URL 中的 token)")
        print("   - FEISHU_TABLE_ID")
        print("   - FEISHU_USER_ID (接收私聊消息的用户 ID)")
    
    client = FeishuClient()
    
    results = {}
    
    results["token"] = check_get_token(client)
    
    if results["token"]:
        results["private_message"] = check_send_private_message(client)
        results["task_card"] = check_task_card(client)
        results["create_record"] = check_create_record(client)
    
    print_separator("测试结果汇总")
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    print(f"[OK] 通过: {passed}")
    print(f"[FAIL] 失败: {failed}")
    print(f"[SKIP] 跳过: {skipped}")
    
    for test_name, result in results.items():
        status = "[OK]" if result is True else ("[FAIL]" if result is False else "[SKIP]")
        print(f"   {test_name}: {status}")
    
    print("\n📝 注意: 实际使用时，表格记录只在用户确认后才创建")
    print("   请使用 tests/test_callback_server.py 测试完整流程")
    
    if failed > 0:
        print("\n[FAIL] 部分测试失败，请检查配置和网络连接")
        return 1
    elif passed > 0:
        print("\n[OK] 飞书对接测试通过!")
        return 0
    else:
        print("\n[WARN] 所有测试都被跳过，请配置必要的环境变量")
        return 2


if __name__ == "__main__":
    exit(main())
