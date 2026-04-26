# -*- coding: utf-8 -*-
import sys
import ntwork

wework = ntwork.WeWork()
wework.open(smart=True)
wework.wait_login()

print("Login successful. Waiting for messages...")
print("=" * 50)

# Try using on_recv instead of on
wework.on_recv(lambda w, m: print(f"\non_recv: type={m.get('type')}, data={str(m.get('data',{}))[:100]}"))

def on_message(wework_instance, message):
    msg_type = message.get("type", 0)
    data = message.get("data", {})
    print(f"\n[on callback] type: {msg_type}")
    if msg_type == ntwork.MT_RECV_TEXT_MSG:
        print(f"  Content: {data.get('content', '')}")
        print(f"  From: {data.get('sender_name', 'unknown')}")
        print(f"  To: {data.get('conversation_id', '')}")

wework.on(ntwork.MT_ALL, on_message)

try:
    while True:
        pass
except KeyboardInterrupt:
    ntwork.exit_()
    sys.exit()