import asyncio
import json
import os
import requests
from dotenv import load_dotenv
from lark_oapi.ws.pb.pbbp2_pb2 import Frame
from lark_oapi.ws.enum import FrameType, MessageType
from lark_oapi.ws.const import HEADER_MESSAGE_ID, HEADER_TYPE, HEADER_SUM, HEADER_SEQ

load_dotenv()

APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")

async def main():
    import websockets

    url = "https://open.feishu.cn/callback/ws/endpoint"
    resp = requests.post(url, headers={"locale": "zh"}, json={
        "AppID": APP_ID,
        "AppSecret": APP_SECRET,
    }, timeout=10)
    data = resp.json()["data"]
    ws_url = data["URL"]
    print(f"Connecting to: {ws_url[:80]}...")

    async with websockets.connect(ws_url) as ws:
        print("Connected! Waiting for raw messages...")
        msg_count = 0
        try:
            async for raw_msg in ws:
                msg_count += 1
                frame = Frame()
                frame.ParseFromString(raw_msg)
                ft = FrameType(frame.method)
                print(f"\n=== Frame #{msg_count} ===")
                print(f"  FrameType: {ft.name}")

                hs = frame.headers
                headers_dict = {}
                for h in hs:
                    headers_dict[h.key] = h.value
                print(f"  Headers: {headers_dict}")

                if frame.payload:
                    payload_str = frame.payload.decode("utf-8", errors="replace")
                    print(f"  Payload: {payload_str[:300]}")

                if ft == FrameType.CONTROL:
                    type_ = headers_dict.get(HEADER_TYPE, "")
                    print(f"  Control type: {type_}")
                elif ft == FrameType.DATA:
                    type_ = headers_dict.get(HEADER_TYPE, "")
                    print(f"  Data type: {type_}")

        except Exception as e:
            print(f"Error: {e}")

    print(f"\nTotal frames received: {msg_count}")

asyncio.run(main())
