# pc_agent_relay.py
"""
Updated PC agent to connect to cloud relay server instead of direct WebSocket.
"""

import asyncio
import json
import logging
from typing import Any, Dict
import pyautogui
import websockets
import os
import socket
import argparse
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pc_agent')

pyautogui.FAILSAFE = True

# ==========================================================
# Configuration
# ==========================================================
RELAY_URL = os.environ.get('RELAY_URL', 'wss://phone-controller-1.onrender.com')
TOKEN = os.environ.get('PC_AGENT_TOKEN', 'my-secret-token')

# ==========================================================
# Command handlers (same as before)
# ==========================================================
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

# ==========================================================
# Relay client connection
# ==========================================================
async def connect_to_relay():
    # Build WebSocket URL with query parameters
    params = {
        'token': TOKEN,
        'client': 'pc'
    }
    query_string = urllib.parse.urlencode(params)
    ws_url = f"{RELAY_URL}?{query_string}"
    
    logger.info(f'Connecting to relay: {ws_url}')
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info('Connected to relay server as PC client')
            
            # Listen for messages from relay (from phone)
            async for message in websocket:
                await handle_relay_message(websocket, message)
                
    except Exception as e:
        logger.error(f'Connection failed: {e}')
        # Optional: Add reconnection logic here

async def handle_relay_message(websocket, message):
    """Handle messages received from relay server"""
    try:
        data = json.loads(message)
        logger.info('Received from relay: %s', data)
        
        # Handle relay status messages
        if data.get('type') == 'relay_status':
            if data.get('phone_connected'):
                logger.info('Phone connected to relay')
            elif data.get('phone_connected') is False:
                logger.info('Phone disconnected from relay')
            return
        
        # Handle authentication responses
        if data.get('auth') is not None:
            logger.info('Authentication response: %s', data)
            return
            
        # Process regular commands
        response = await process_message(message)
        if websocket.open:
            await websocket.send(json.dumps(response))
            
    except json.JSONDecodeError:
        logger.error('Invalid JSON from relay: %s', message)
    except Exception as e:
        logger.error('Error handling relay message: %s', e)

async def process_message(message: str) -> Dict[str, Any]:
    """Parse and execute a JSON message. Returns a response dict."""
    try:
        data = json.loads(message)
        if not isinstance(data, dict):
            return {'ok': False, 'error': 'Payload must be a JSON object.'}

        cmd_type = data.get('type')
        if cmd_type not in COMMAND_HANDLERS:
            return {'ok': False, 'error': f'Unknown command type: {cmd_type}'}

        handler = COMMAND_HANDLERS[cmd_type]
        await handler(data)
        return {'ok': True}
    except json.JSONDecodeError:
        return {'ok': False, 'error': 'Invalid JSON'}
    except Exception as exc:
        logger.exception('Error processing message')
        return {'ok': False, 'error': str(exc)}

# ==========================================================
# Main execution
# ==========================================================
async def main():
    logger.info('Starting PC Agent (Relay Mode)')
    logger.info('Token: %s', TOKEN)
    logger.info('Relay URL: %s', RELAY_URL)
    
    # Keep trying to connect/reconnect
    while True:
        try:
            await connect_to_relay()
        except Exception as e:
            logger.error('Disconnected from relay: %s', e)
            logger.info('Reconnecting in 5 seconds...')
            await asyncio.sleep(5)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Shutting down...')