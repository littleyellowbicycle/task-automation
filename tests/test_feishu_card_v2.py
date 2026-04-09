"""
Test Feishu card with different format.
"""
import sys
import os
import json
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu_recorder.client import FeishuClient
from dotenv import load_dotenv

load_dotenv()


def main():
    print("Testing Feishu card format...")
    
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    user_id = os.getenv("FEISHU_USER_ID", "a5566bge")
    
    print(f"User ID: {user_id}")
    
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    token_resp = requests.post(token_url, json={
        "app_id": app_id,
        "app_secret": app_secret
    })
    token = token_resp.json().get("tenant_access_token")
    print(f"Token obtained: {token[:20]}...")
    
    callback_url = "http://localhost:8086"
    task_id = "test_card_002"
    
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "任务审批"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**任务摘要**\n创建Python计算器脚本"
                }
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "确认执行"
                        },
                        "type": "primary",
                        "url": f"{callback_url}/decision?task_id={task_id}&action=approve"
                    }
                ]
            }
        ]
    }
    
    content = card
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = {"receive_id_type": "user_id"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    
    payload = {
        "receive_id": user_id,
        "msg_type": "interactive",
        "content": json.dumps(content)
    }
    
    print(f"\nPayload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    resp = requests.post(url, params=params, json=payload, headers=headers)
    print(f"\nResponse: {resp.status_code}")
    print(f"Body: {resp.json()}")


if __name__ == "__main__":
    main()
