import lark_oapi as lark
from lark_oapi.ws import Client as WSClient
from dotenv import load_dotenv
import os
import time

load_dotenv()

received = []

def on_card(data):
    print(f"CARD ACTION: {lark.JSON.marshal(data)}")
    received.append(data)

def on_message(data):
    print(f"MESSAGE: {lark.JSON.marshal(data)}")
    received.append(data)

event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_card_action_trigger(on_card)
    .register_p2_im_message_receive_v1(on_message)
    .build()
)

cli = lark.ws.Client(
    os.getenv("FEISHU_APP_ID"),
    os.getenv("FEISHU_APP_SECRET"),
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)

import threading
t = threading.Thread(target=cli.start, daemon=True)
t.start()

print("Official SDK test started. Waiting 120s...")
for i in range(120):
    time.sleep(1)
    if received:
        print(f"SUCCESS! {len(received)} events received")
        break
    if i % 20 == 0 and i > 0:
        print(f"  ... {i}s")

if not received:
    print("TIMEOUT")
