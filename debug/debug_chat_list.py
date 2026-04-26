# -*- coding: utf-8 -*-
import sys
import ntwork

wework = ntwork.WeWork()
wework.open(smart=True)
wework.wait_login()

print("Getting chat list...")
try:
    chats = wework.get_chat_list()
    print(f"Chat list ({len(chats)} chats):")
    for chat in chats[:20]:
        cid = chat.get('conversation_id', '')
        name = chat.get('name', chat.get('nickname', 'unknown'))
        print(f"  {cid}: {name}")
except Exception as e:
    print(f"get_chat_list error: {e}")

print("\nTrying to get room list...")
try:
    rooms = wework.get_room_list()
    print(f"Room list ({len(rooms)} rooms):")
    for room in rooms[:20]:
        print(f"  {room}")
except Exception as e:
    print(f"get_room_list error: {e}")

print("\nListening for messages... Press Ctrl+C to exit")
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
        keys = list(data.keys())[:5]
        print(f"  Data keys: {keys}")

wework.on(ntwork.MT_ALL, on_message)

try:
    while True:
        pass
except KeyboardInterrupt:
    ntwork.exit_()
    sys.exit()