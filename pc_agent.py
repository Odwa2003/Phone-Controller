"""
PC agent: a simple WebSocket server that accepts JSON commands and executes safe pyautogui actions.

Security: now requires a pairing token before commands work.
Store the same token on both phone and PC sides.
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pc_agent')

pyautogui.FAILSAFE = True

# ==========================================================
# Configuration
# ==========================================================
HOST = os.environ.get('PC_AGENT_HOST', '196.253.65.236') 
PORT = 8765

# 🔐 Pairing token — must match the one in your web client
TOKEN = os.environ.get('PC_AGENT_TOKEN','my-secret-token')  # e.g., setx PC_AGENT_TOKEN "my-secret-token"

# ==========================================================
# Command handlers
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
# Core message logic
# ==========================================================
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
# WebSocket handler
# ==========================================================
async def ws_handler(ws: websockets.WebSocketServerProtocol, path=None):
    addr = getattr(ws, 'remote_address', None)
    logger.info('Client connected: %s', addr)

    ws.authenticated = False
    ws._auth_attempts = 0

    try:
        async for message in ws:
            logger.info('Received message: %s', message)
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await ws.send(json.dumps({'ok': False, 'error': 'Invalid JSON'}))
                continue

            # 🔐 Authentication step
            if TOKEN:
                if not getattr(ws, 'authenticated', False):
                    if data.get('type') == 'auth':
                        provided = data.get('token')
                        if provided == TOKEN:
                            ws.authenticated = True
                            await ws.send(json.dumps({'ok': True, 'auth': True}))
                            logger.info('Client %s authenticated', addr)
                        else:
                            ws._auth_attempts += 1
                            await ws.send(json.dumps({'ok': False, 'error': 'Authentication failed'}))
                            logger.warning('Authentication failed for %s (attempt %d)', addr, ws._auth_attempts)
                            if ws._auth_attempts >= 3:
                                logger.warning('Closing connection after 3 failed auth attempts: %s', addr)
                                await ws.close()
                    else:
                        await ws.send(json.dumps({'ok': False, 'error': 'Not authenticated'}))
                    continue  # Skip command execution until authenticated

            # If authenticated or TOKEN not required
            response = await process_message(message)
            await ws.send(json.dumps(response))

    except websockets.ConnectionClosed:
        logger.info('Client disconnected: %s', addr)

# ==========================================================
# Server setup
# ==========================================================
async def _run_server(bind_host: str):
    logger.info('Starting PC agent on ws://%s:%d', bind_host, PORT)
    async with websockets.serve(ws_handler, bind_host, PORT):
        logger.info('Server is ready and waiting for clients...')
        await asyncio.Future()  # Run forever

def main():
    global HOST
    parser = argparse.ArgumentParser(description='PC Agent WebSocket server')
    parser.add_argument('--host', '-H', help='Host/IP to bind to (e.g. 0.0.0.0)')
    args = parser.parse_args()

    desired_host = args.host or HOST
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((desired_host, 0))
        bind_host = desired_host
    except OSError:
        logger.warning('Could not bind to %s — falling back to 0.0.0.0 (all interfaces).', desired_host)
        bind_host = '0.0.0.0'

    HOST = bind_host

    try:
        asyncio.run(_run_server(HOST))
    except KeyboardInterrupt:
        logger.info('Shutting down...')

# ==========================================================
# Entry point
# ==========================================================
if __name__ == '__main__':
    main()
