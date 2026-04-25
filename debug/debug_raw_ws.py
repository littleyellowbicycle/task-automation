import asyncio
import json
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")

async def main():
    import websockets

    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(token_url, json={
        "app_id": APP_ID,
        "app_secret": APP_SECRET,
    }, timeout=10)
    token_data = resp.json()
    tenant_token = token_data.get("tenant_access_token")
    print(f"Token obtained: {tenant_token[:20]}...")

    endpoint_url = "https://open.feishu.cn/open-apis/callback/ws/endpoint"
    resp = requests.post(endpoint_url, headers={
        "Authorization": f"Bearer {tenant_token}",
    }, json={}, timeout=10)
    endpoint_data = resp.json()
    print(f"Endpoint response: {json.dumps(endpoint_data, indent=2)[:500]}")

    ws_url = endpoint_data.get("data", {}).get("endpoint")
    if not ws_url:
        print("No WebSocket endpoint URL found!")
        print("Full response:", json.dumps(endpoint_data, indent=2))
        return

    print(f"Connecting to: {ws_url[:100]}...")

    async with websockets.connect(ws_url) as ws:
        print("Connected! Waiting for messages...")
        try:
            async for message in ws:
                print(f">>> RAW MESSAGE: {message[:500]}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")

asyncio.run(main())
