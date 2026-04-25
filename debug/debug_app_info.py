import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")

token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
resp = requests.post(token_url, json={
    "app_id": APP_ID,
    "app_secret": APP_SECRET,
}, timeout=10)
token = resp.json().get("tenant_access_token")

headers = {"Authorization": f"Bearer {token}"}
api_base = "https://open.feishu.cn/open-apis"

apis = [
    (f"/application/v6/applications/{APP_ID}?lang=zh_cn", "GET"),
    (f"/event/v1/outbound_ip", "GET"),
]

for path, method in apis:
    url = api_base + path
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"\n{method} {path}")
    print(f"  Status: {resp.status_code}")
    try:
        data = resp.json()
        print(f"  Response: {json.dumps(data, indent=2, ensure_ascii=False)[:1500]}")
    except:
        print(f"  Response: {resp.text[:300]}")
