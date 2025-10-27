# pc_agent_relay.py
import asyncio
import json
import logging
from typing import Any, Dict
import pyautogui
import websockets
import os
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pc_agent')

pyautogui.FAILSAFE = True

# Configuration
RELAY_URL = os.environ.get('RELAY_URL', 'wss://phone-controller-1.onrender.com')
TOKEN = os.environ.get('PC_AGENT_TOKEN', 'helloworld')

# Command handlers (same as before)
async def handle_click(payload: Dict[str, Any]):
    x = payload.get('x')
    y = payload.get('y')
    button = payload.get('button', 'left')
    logger.info('Performing click: x=%s y=%s button=%s', x, y, button)
    try:
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, button=button)
        else:
            pyautogui.click(button=button)
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')

async def handle_type(payload: Dict[str, Any]):
    text = payload.get('text', '')
    interval = float(payload.get('interval', 0.05))
    logger.info('Typing text: %s', text)
    try:
        pyautogui.write(text, interval=interval)
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')

async def handle_move(payload: Dict[str, Any]):
    x = payload.get('x')
    y = payload.get('y')
    duration = float(payload.get('duration', 0.1))
    logger.info('Moving mouse to x=%s y=%s duration=%s', x, y, duration)
    try:
        if x is not None and y is not None:
            pyautogui.moveTo(x, y, duration=duration)
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')

COMMAND_HANDLERS = {
    'click': handle_click,
    'type': handle_type,
    'move': handle_move,
}

async def connect_to_relay():
    import urllib.parse
    params = {'token': TOKEN, 'client': 'pc'}
    query_string = urllib.parse.urlencode(params)
    ws_url = f"{RELAY_URL}?{query_string}"
    
    logger.info(f'Connecting to relay: {ws_url}')
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info('✅ Connected to relay server as PC client')
            
            # Send authentication (if your relay expects it)
            await websocket.send(json.dumps({'type': 'auth', 'token': TOKEN}))
            
            # Listen for messages from relay
            async for message in websocket:
                await handle_relay_message(websocket, message)
                
    except Exception as e:
        logger.error(f'❌ Connection failed: {e}')

async def handle_relay_message(websocket, message):
    try:
        data = json.loads(message)
        logger.info('Received command: %s', data)
        
        # Handle status messages
        if data.get('type') == 'relay_status':
            logger.info('Relay status: %s', data)
            return
            
        # Process commands
        cmd_type = data.get('type')
        if cmd_type in COMMAND_HANDLERS:
            handler = COMMAND_HANDLERS[cmd_type]
            await handler(data)
            # Send success response
            if websocket.open:
                await websocket.send(json.dumps({'ok': True, 'command': cmd_type}))
        else:
            logger.warning('Unknown command type: %s', cmd_type)
            
    except Exception as e:
        logger.error('Error handling message: %s', e)
        if websocket.open:
            await websocket.send(json.dumps({'ok': False, 'error': str(e)}))

async def main():
    logger.info('🚀 Starting PC Agent (Relay Mode)')
    logger.info('🔑 Token: %s', TOKEN)
    logger.info('🌐 Relay URL: %s', RELAY_URL)
    
    # Keep trying to connect/reconnect
    while True:
        try:
            await connect_to_relay()
        except Exception as e:
            logger.error('Disconnected from relay: %s', e)
            logger.info('Reconnecting in 5 seconds...')
            await asyncio.sleep(5)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--relay-url', help='Relay server URL')
    parser.add_argument('--token', help='Authentication token')
    args = parser.parse_args()
    
    if args.relay_url:
        RELAY_URL = args.relay_url
    if args.token:
        TOKEN = args.token
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Shutting down...')