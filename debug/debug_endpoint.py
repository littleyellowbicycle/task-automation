import asyncio
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")

token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
resp = requests.post(token_url, json={
    "app_id": APP_ID,
    "app_secret": APP_SECRET,
}, timeout=10)
tenant_token = resp.json().get("tenant_access_token")
print(f"Token: {tenant_token[:20]}...")

endpoint_url = "https://open.feishu.cn/open-apis/callback/ws/endpoint"
resp = requests.post(endpoint_url, headers={
    "Authorization": f"Bearer {tenant_token}",
}, json={}, timeout=10)
print(f"Status: {resp.status_code}")
print(f"Response text: {resp.text[:500]}")
