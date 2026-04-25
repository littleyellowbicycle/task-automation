import * as Lark from '@larksuiteoapi/node-sdk';
import 'dotenv/config';

const appId = process.env.FEISHU_APP_ID;
const appSecret = process.env.FEISHU_APP_SECRET;

console.log('App ID:', appId);

const eventHandler = new Lark.EventDispatcher({}).register({
    'im.message.receive_v1': async (data) => {
        console.log('>>> MESSAGE RECEIVED:', JSON.stringify(data).substring(0, 200));
    },
    'card.action.trigger': async (data) => {
        console.log('>>> CARD ACTION:', JSON.stringify(data).substring(0, 200));
    },
});

const wsClient = new Lark.WSClient({
    appId,
    appSecret,
    loggerLevel: Lark.LoggerLevel.debug,
});

console.log('Starting Node.js WebSocket client...');
wsClient.start({
    eventDispatcher: eventHandler,
});
