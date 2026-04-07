"""
获取飞书用户 ID 的辅助脚本

使用方法:
python tests/get_feishu_user_id.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests


def get_user_id():
    """获取当前用户信息"""
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    if not app_id or not app_secret:
        print("请先配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return
    
    # 获取 tenant_access_token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    response = requests.post(url, json={
        "app_id": app_id,
        "app_secret": app_secret,
    })
    
    data = response.json()
    if data.get("code") != 0:
        print(f"获取 token 失败: {data}")
        return
    
    token = data.get("tenant_access_token")
    print(f"✅ Token 获取成功")
    
    # 获取用户列表
    url = "https://open.feishu.cn/open-apis/contact/v3/users"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page_size": 10}
    
    response = requests.get(url, headers=headers, params=params)
    
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.text[:500]}")
    
    try:
        data = response.json()
    except Exception as e:
        print(f"JSON 解析失败: {e}")
        return
    
    if data.get("code") == 0:
        users = data.get("data", {}).get("items", [])
        print(f"\n找到 {len(users)} 个用户:\n")
        print(f"{'用户名':<20} {'User ID':<30} {'Open ID':<30}")
        print("-" * 80)
        for user in users:
            name = user.get("name", "未知")
            user_id = user.get("user_id", "")
            open_id = user.get("open_id", "")
            print(f"{name:<20} {user_id:<30} {open_id:<30}")
        
        print("\n请将您的 User ID 填入 .env 文件的 FEISHU_USER_ID")
    else:
        print(f"获取用户列表失败: {data}")
        print("\n提示: 请确保应用有以下权限:")
        print("  - contact:user.base:readonly (获取用户基本信息)")


if __name__ == "__main__":
    get_user_id()
