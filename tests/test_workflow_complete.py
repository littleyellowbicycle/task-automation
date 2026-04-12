import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import httpx
from datetime import datetime, timezone


GATEWAY_URL = "http://localhost:8000"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_workflow():
    print("=" * 60)
    print("Testing Complete Workflow v2: Gateway API")
    print("=" * 60)

    print("\n1. Checking gateway health...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{GATEWAY_URL}/health")
            health = r.json()
            print(f"   Status: {health['status']}")
    except Exception as e:
        pytest.skip(f"Gateway not available: {e}")

    print("\n2. Sending test message...")
    message = {
        "content": "项目发布：开发一个用户登录功能，使用 Python Flask 框架",
        "sender_id": "test_user",
        "sender_name": "Test User",
        "conversation_id": "test_group_001",
        "conversation_type": "group",
        "platform": "wework",
        "listener_type": "test",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{GATEWAY_URL}/api/v1/listener/msg", json=message)
        result = r.json()

    task_id = result.get("task_id")
    print(f"   Task ID: {task_id}")
    print(f"   Result: {result}")

    if not task_id:
        pytest.fail("Failed to create task")

    print("\n3. Checking task status...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{GATEWAY_URL}/api/v1/tasks/{task_id}")
        task_data = r.json()
        print(f"   Status: {task_data.get('data', {}).get('status')}")

    print(f"\n4. Approving task {task_id}...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{GATEWAY_URL}/api/v1/decisions", json={
            "task_id": task_id,
            "action": "approve",
        })
        decision_result = r.json()
        print(f"   Decision result: {decision_result}")

    await asyncio.sleep(2)

    print("\n5. Checking final task status...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{GATEWAY_URL}/api/v1/tasks/{task_id}")
        task_data = r.json()
        final_status = task_data.get("data", {}).get("status")
        print(f"   Final status: {final_status}")

    print("\n6. Checking queue status...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{GATEWAY_URL}/api/v1/queue/status")
        queue_data = r.json()
        print(f"   Queue: {queue_data.get('data')}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_feishu_callback():
    print("=" * 60)
    print("Testing Feishu Callback Endpoint")
    print("=" * 60)

    print("\n1. Testing URL verification...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{GATEWAY_URL}/api/v1/feishu/callback", json={
                "type": "url_verification",
                "challenge": "test_challenge_123",
            })
            result = r.json()
            print(f"   Challenge response: {result}")
    except Exception as e:
        pytest.skip(f"Gateway not available: {e}")

    if result.get("challenge") == "test_challenge_123":
        print("   URL verification OK!")
    else:
        pytest.fail("URL verification FAILED!")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test workflow v2")
    parser.add_argument("--feishu", action="store_true", help="Test Feishu callback only")
    args = parser.parse_args()

    if args.feishu:
        asyncio.run(test_feishu_callback())
    else:
        asyncio.run(test_complete_workflow())
