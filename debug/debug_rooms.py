# -*- coding: utf-8 -*-
import sys
import ntwork

wework = ntwork.WeWork()
wework.open(smart=True)
wework.wait_login()

print("Getting rooms...")
try:
    rooms = wework.get_rooms()
    print(f"Rooms ({len(rooms)}):")
    for room in rooms[:30]:
        print(f"  {room}")
except Exception as e:
    print(f"get_rooms error: {e}")

print("\n" + "=" * 50)
print("Listening for messages... Press Ctrl+C to exit")

def on_message(wework_instance, message):
    msg_type = message.get("type", 0)
    data = message.get("data", {})
    print(f"\n[type: {msg_type}]")
    if msg_type == ntwork.MT_RECV_TEXT_MSG:
        sender = data.get('sender_name', data.get('sender', 'unknown'))
        conv_id = data.get('conversation_id', '')
        content = data.get('content', '')[:100]
        print(f"  From: {sender}")
        print(f"  Conversation: {conv_id}")
        print(f"  Content: {content}")

wework.on(ntwork.MT_ALL, on_message)

try:
    while True:
        pass
except KeyboardInterrupt:
    ntwork.exit_()
    sys.exit()