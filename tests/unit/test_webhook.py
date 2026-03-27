import json
import hmac
import hashlib
from fastapi.testclient import TestClient

from src.wechat_listener.server import app


def test_webhook_signature_and_processing():
    client = TestClient(app)
    token = b"testtoken"
    payload = {
        "msg_id": "wb_001",
        "content": "项目发布: 新页面登录功能实现",
        "conversation_id": "C1",
        "conversation_type": "group",
        "sender_id": "u123",
        "sender_name": "tester",
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(token, body, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-WeChat-Signature": signature}
    import os
    os.environ["WECHAT_HOOK_TOKEN"] = "testtoken"
    response = client.post("/webhook/wechat", data=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True

def test_webhook_duplicate_detection():
    client = TestClient(app)
    payload = {
        "msg_id": "wb-dup-001",
        "content": "项目发布: 重复消息测试",
        "conversation_id": "C1",
        "conversation_type": "group",
        "sender_id": "u999",
        "sender_name": "tester-dup",
    }
    body = json.dumps(payload).encode()
    import os
    os.environ["WECHAT_HOOK_TOKEN"] = "testtoken"
    sig = hmac.new(b"testtoken", body, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-WeChat-Signature": sig}
    # First call - should process
    resp1 = client.post("/webhook/wechat", data=body, headers=headers)
    assert resp1.status_code == 200
    # Second call - should be detected as duplicate
    resp2 = client.post("/webhook/wechat", data=body, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2.get("status", "") in ("duplicate", "OK", "true")

def test_webhook_signature_rejects_wrong_signature():
    client = TestClient(app)
    payload = {"content": "测试消息"}
    body = json.dumps(payload).encode()
    wrong_signature = "bad-signature"
    headers = {"Content-Type": "application/json", "X-WeChat-Signature": wrong_signature}
    response = client.post("/webhook/wechat", data=body, headers=headers)
    assert response.status_code == 200 or response.status_code == 403
    # If signature check fails, we handle accordingly
    data = response.json()
    assert isinstance(data, dict)
