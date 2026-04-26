# -*- coding: utf-8 -*-
import sys
import ntwork

wework = ntwork.WeWork()
wework.open(smart=True)
wework.wait_login()

print("Listening for ALL messages... Press Ctrl+C to exit")
print("=" * 50)

def on_message(wework_instance, message):
    msg_type = message.get("type", 0)
    data = message.get("data", {})
    print(f"\n[type: {msg_type}]")
    if msg_type == ntwork.MT_RECV_TEXT_MSG:
        print(f"  From: {data.get('sender_name', 'unknown')}")
        print(f"  Conversation: {data.get('conversation_id', '')}")
        print(f"  Content: {data.get('content', '')[:100]}")
    elif data:
        # Print first few keys of data
        keys = list(data.keys())[:5]
        print(f"  Data keys: {keys}")

wework.on(ntwork.MT_ALL, on_message)

try:
    while True:
        pass
except KeyboardInterrupt:
    ntwork.exit_()
    sys.exit()