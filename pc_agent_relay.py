# pc_agent_relay_fixed.py
import asyncio
import json
import logging
from typing import Any, Dict
import pyautogui
import websockets
import os
import argparse
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pc_agent')

pyautogui.FAILSAFE = True

# Configuration
RELAY_URL = os.environ.get('RELAY_URL', 'wss://phone-controller-1.onrender.com')
TOKEN = os.environ.get('PC_AGENT_TOKEN', 'helloworld')

# Command handlers
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

async def handle_relay_message(websocket, message):
    """Handle messages received from relay server"""
    try:
        data = json.loads(message)
        logger.info('Received command: %s', data)
        
        # Handle relay status messages
        if data.get('type') == 'relay_status':
            if data.get('phone_connected'):
                logger.info('📱 Phone connected to relay')
            elif data.get('phone_connected') is False:
                logger.info('📱 Phone disconnected from relay')
            return
        
        # Handle authentication messages (just acknowledge them)
        if data.get('type') == 'auth':
            logger.info('🔐 Auth request received')
            # Send auth response back to phone through relay
            response = {'ok': True, 'auth': True, 'type': 'auth_response'}
            await websocket.send(json.dumps(response))
            return
            
        # Process regular commands
        cmd_type = data.get('type')
        if cmd_type in COMMAND_HANDLERS:
            handler = COMMAND_HANDLERS[cmd_type]
            await handler(data)
            # Send success response
            response = {'ok': True, 'command': cmd_type}
            await websocket.send(json.dumps(response))
            logger.info('✅ Command executed: %s', cmd_type)
        else:
            logger.warning('❌ Unknown command type: %s', cmd_type)
            response = {'ok': False, 'error': f'Unknown command type: {cmd_type}'}
            await websocket.send(json.dumps(response))
            
    except Exception as e:
        logger.error('❌ Error handling message: %s', e)
        try:
            response = {'ok': False, 'error': str(e)}
            await websocket.send(json.dumps(response))
        except:
            logger.error('Failed to send error response')

async def connect_to_relay():
    params = {'token': TOKEN, 'client': 'pc'}
    query_string = urllib.parse.urlencode(params)
    ws_url = f"{RELAY_URL}?{query_string}"
    
    logger.info('🔗 Connecting to relay: %s', ws_url)
    
    try:
        # Don't use async with - it closes the connection automatically
        websocket = await websockets.connect(ws_url, ping_interval=20, ping_timeout=10)
        logger.info('✅ Connected to relay server as PC client')
        
        # Send initial auth to identify ourselves
        await websocket.send(json.dumps({'type': 'auth', 'token': TOKEN}))
        
        # Listen for messages continuously
        async for message in websocket:
            await handle_relay_message(websocket, message)
            
    except websockets.exceptions.ConnectionClosed:
        logger.warning('🔌 Connection closed by relay')
    except Exception as e:
        logger.error('❌ Connection error: %s', e)
    finally:
        # Clean up if websocket exists
        if 'websocket' in locals():
            await websocket.close()
        logger.info('🔌 Disconnected from relay')

async def main():
    logger.info('🚀 Starting PC Agent (Relay Mode)')
    logger.info('🔑 Token: %s', TOKEN)
    logger.info('🌐 Relay URL: %s', RELAY_URL)
    
    # Keep trying to connect/reconnect
    reconnect_delay = 5
    while True:
        try:
            await connect_to_relay()
        except KeyboardInterrupt:
            logger.info('Received interrupt, shutting down...')
            break
        except Exception as e:
            logger.error('Unexpected error: %s', e)
        
        logger.info('🔄 Reconnecting in %d seconds...', reconnect_delay)
        await asyncio.sleep(reconnect_delay)

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
        logger.info('👋 Shutting down...')