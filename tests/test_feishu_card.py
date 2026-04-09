"""
Test Feishu card with correct format.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu_recorder.client import FeishuClient
from dotenv import load_dotenv

load_dotenv()


def main():
    print("Testing Feishu interactive card...")
    
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET"),
        table_id=os.getenv("FEISHU_TABLE_ID"),
    )
    
    user_id = os.getenv("FEISHU_USER_ID", "a5566bge")
    print(f"User ID: {user_id}")
    
    callback_url = "http://localhost:8086"
    task_id = "test_card_001"
    
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
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**技术栈**: Python"
                }
            },
            {
                "tag": "hr"
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
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "取消"
                        },
                        "type": "danger",
                        "url": f"{callback_url}/decision?task_id={task_id}&action=reject"
                    }
                ]
            }
        ]
    }
    
    content = {
        "type": "interactive",
        "card": card
    }
    
    print(f"\nCard content:\n{json.dumps(content, indent=2, ensure_ascii=False)}")
    
    message_id = feishu_client.send_private_message(
        user_id=user_id,
        content=json.dumps(content),
        msg_type="interactive",
    )
    print(f"\nResult: {'Success' if message_id else 'Failed'}")
    if message_id:
        print(f"Message ID: {message_id}")


if __name__ == "__main__":
    main()
