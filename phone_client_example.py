"""
Phone client example: connects to the local PC agent and sends a few JSON commands.
This is a test script meant to run on the same machine or another device that can reach the PC.
"""
import asyncio
import json
import logging

import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('phone_client')

HOST = '127.0.0.1'
PORT = 8765


async def send_command(cmd: dict):
    uri = f'ws://{HOST}:{PORT}'
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps(cmd))
        resp = await ws.recv()
        logger.info('Response: %s', resp)


async def main():
    # Example sequence: move, type, click
    await send_command({'type': 'move', 'x': 100, 'y': 100, 'duration': 0.2})
    await send_command({'type': 'type', 'text': 'Hello from phone', 'interval': 0.05})
    await send_command({'type': 'click', 'button': 'left'})


if __name__ == '__main__':
    asyncio.run(main())
