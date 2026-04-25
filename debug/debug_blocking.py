import lark_oapi as lark
from dotenv import load_dotenv
import os

load_dotenv()

received = []

def on_card(data):
    print(f"CARD: {lark.JSON.marshal(data)[:300]}")
    received.append(data)

def on_message(data):
    print(f"MSG: {lark.JSON.marshal(data)[:300]}")
    received.append(data)

handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_card_action_trigger(on_card)
    .register_p2_im_message_receive_v1(on_message)
    .build()
)

cli = lark.ws.Client(
    os.getenv("FEISHU_APP_ID"),
    os.getenv("FEISHU_APP_SECRET"),
    event_handler=handler,
    log_level=lark.LogLevel.DEBUG,
)

print("Starting BLOCKING WebSocket client...")
print("Please send a message to the bot or click a card button")
print("Press Ctrl+C to stop")
print()

cli.start()
