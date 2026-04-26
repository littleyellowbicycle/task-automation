# -*- coding: utf-8 -*-
import sys
import ntwork

wework = ntwork.WeWork()

print("Opening WeWork with smart=True (attach to existing instance)...")
wework.open(smart=True)

print("Waiting for login...")
wework.wait_login()

print("Login successful!")
print("Available methods:", dir(wework))

# Try to get current user info
try:
    print("\nAttempting to get user info...")
    wework.get_login_info()
except Exception as e:
    print(f"get_login_info: {e}")

# Try to list chats
try:
    print("\nAttempting to get chat list...")
    chats = wework.get_chat_list()
    print(f"Chat list: {chats}")
except Exception as e:
    print(f"get_chat_list: {e}")

# Send a test message
print("\nSending test message to FILEASSIST...")
result = wework.send_text(conversation_id="FILEASSIST", content="debug test from ntwork")
print(f"Send result: {result}")

try:
    while True:
        pass
except KeyboardInterrupt:
    ntwork.exit_()
    sys.exit()