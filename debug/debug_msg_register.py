# -*- coding: utf-8 -*-
import sys
import ntwork

wework = ntwork.WeWork()
wework.open(smart=True)
wework.wait_login()

print("Login successful. Listening for text messages...")
print("=" * 50)

# Register callback using decorator
@wework.msg_register(ntwork.MT_RECV_TEXT_MSG)
def on_recv_text_msg(wework_instance, message):
    data = message["data"]
    sender_user_id = data["sender"]
    conversation_id = data["conversation_id"]
    content = data.get("content", "")

    print(f"\n[收到消息]")
    print(f"  发送者ID: {sender_user_id}")
    print(f"  会话ID: {conversation_id}")
    print(f"  内容: {content}")

try:
    while True:
        pass
except KeyboardInterrupt:
    ntwork.exit_()
    sys.exit()