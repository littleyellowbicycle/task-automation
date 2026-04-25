from dotenv import load_dotenv
load_dotenv()
import os
import time
import lark_oapi as lark
from lark_oapi.ws import Client as WSClient
from lark_oapi.ws.client import MessageType
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger, P2CardActionTriggerResponse

original_handle_data_frame = WSClient._handle_data_frame

async def debug_handle_data_frame(self, frame):
    from lark_oapi.ws.client import (
        HEADER_MESSAGE_ID, HEADER_TRACE_ID, HEADER_SUM, HEADER_SEQ, HEADER_TYPE,
        HEADER_BIZ_RT, UTF_8, Response, _get_by_key,
    )
    import base64, http, time as time_mod
    from lark_oapi.core.model import JSON

    hs = frame.headers
    msg_id = _get_by_key(hs, HEADER_MESSAGE_ID)
    type_ = _get_by_key(hs, HEADER_TYPE)
    sum_ = _get_by_key(hs, HEADER_SUM)
    seq = _get_by_key(hs, HEADER_SEQ)

    pl = frame.payload
    if int(sum_) > 1:
        pl = self._combine(msg_id, int(sum_), int(seq), pl)
        if pl is None:
            return

    message_type = MessageType(type_)
    payload_str = pl.decode('utf-8')
    print(f'>>> FRAME: type={message_type.value}, msg_id={msg_id}, payload={payload_str[:300]}')

    resp = Response(code=http.HTTPStatus.OK)
    try:
        if message_type in (MessageType.EVENT, MessageType.CARD):
            result = self._event_handler.do_without_validation(pl)
            if result is not None:
                resp.data = base64.b64encode(JSON.marshal(result).encode(UTF_8))
        else:
            return
    except Exception as e:
        print(f'>>> ERROR: {e}')
        import traceback
        traceback.print_exc()
        resp = Response(code=http.HTTPStatus.INTERNAL_SERVER_ERROR)

    frame.payload = JSON.marshal(resp).encode(UTF_8)
    await self._write_message(frame.SerializeToString())

WSClient._handle_data_frame = debug_handle_data_frame

received = []

def on_card(data):
    print(f'>>> CARD CALLBACK: task_id={data.event.action.value.get("task_id","")}, action={data.event.action.value.get("action","")}')
    received.append(('card', data))

def on_message(data):
    print(f'>>> MESSAGE CALLBACK')
    received.append(('message', data))

handler = (
    lark.EventDispatcherHandler.builder('', '')
    .register_p2_card_action_trigger(on_card)
    .register_p2_im_message_receive_v1(on_message)
    .build()
)

client = WSClient(
    os.getenv('FEISHU_APP_ID'),
    os.getenv('FEISHU_APP_SECRET'),
    event_handler=handler,
    log_level=lark.LogLevel.DEBUG,
)

import threading
t = threading.Thread(target=client.start, daemon=True)
t.start()
time.sleep(3)

from src.feishu_recorder.feishu_bridge import FeishuBridge
from src.feishu_recorder.models import TaskRecord, TaskStatus

bridge = FeishuBridge(
    app_id=os.getenv('FEISHU_APP_ID'),
    app_secret=os.getenv('FEISHU_APP_SECRET'),
    table_id=os.getenv('FEISHU_TABLE_ID'),
    user_id=os.getenv('FEISHU_USER_ID'),
    use_websocket=True,
)

record = TaskRecord(
    task_id='test-exclusive-ws-001',
    raw_message='Exclusive WS test - click a button',
    summary='Click Approve or Reject',
    tech_stack=['Python'],
    core_features=['WebSocket'],
    status=TaskStatus.PENDING,
)

success = bridge.send_approval_card(record)
print(f'Card sent: {success}')
print('Waiting 120s... Send a message to the bot or click a card button.')
print()

for i in range(120):
    time.sleep(1)
    if received:
        print(f'=== SUCCESS: {len(received)} callback(s) received! ===')
        for r in received:
            print(f'  - {r[0]}')
        break
    if i % 20 == 0 and i > 0:
        print(f'  ... waiting ({i}s)')

if not received:
    print('TIMEOUT: No callback received in 120s')
