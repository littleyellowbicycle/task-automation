import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")

url = "https://open.feishu.cn/callback/ws/endpoint"
resp = requests.post(url, headers={"locale": "zh"}, json={
    "AppID": APP_ID,
    "AppSecret": APP_SECRET,
}, timeout=10)

print(f"Status: {resp.status_code}")
print(f"Response: {json.dumps(resp.json(), indent=2)[:1000]}")
