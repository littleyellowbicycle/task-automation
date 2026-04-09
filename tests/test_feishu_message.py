"""
Test Feishu private message.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu_recorder.client import FeishuClient
from dotenv import load_dotenv

load_dotenv()


def main():
    print("Testing Feishu private message...")
    
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET"),
        table_id=os.getenv("FEISHU_TABLE_ID"),
    )
    
    user_id = os.getenv("FEISHU_USER_ID", "a5566bge")
    print(f"User ID: {user_id}")
    
    print("\n[1] Testing text message...")
    message_id = feishu_client.send_private_message(
        user_id=user_id,
        content=json.dumps({"text": "测试消息：飞书私聊测试成功！"}),
        msg_type="text",
    )
    print(f"Result: {'Success' if message_id else 'Failed'}")
    if message_id:
        print(f"Message ID: {message_id}")
    
    print("\n[2] Testing interactive card...")
    
    card = {
        "type": "template",
        "data": {
            "template_id": "AAqkz9J8p",
            "template_variable": {
                "title": "测试卡片",
                "content": "这是一条测试消息"
            }
        }
    }
    
    message_id = feishu_client.send_private_message(
        user_id=user_id,
        content=json.dumps(card),
        msg_type="interactive",
    )
    print(f"Result: {'Success' if message_id else 'Failed'}")


if __name__ == "__main__":
    main()
