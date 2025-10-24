"""
PC Agent (Relay Version)
------------------------
Connects outbound to a WebSocket relay (e.g., Render server).
Listens for JSON commands relayed from the phone and executes them safely.

Environment variables:
  RELAY_URL  = wss://your-relay.onrender.com
  PAIR_ID    = unique name/code for this PC (e.g., "my_pc" or "pair123")
  PC_TOKEN   = optional secret token for authentication
"""

import asyncio
import json
import os
import pyautogui
import websockets

pyautogui.FAILSAFE = True

RELAY_URL = os.environ.get("RELAY_URL", "wss://phone-controller-s2pe.onrender.com")
PAIR_ID = os.environ.get("PAIR_ID", "pair123")
TOKEN = os.environ.get("PC_TOKEN", "my-secret-token")

async def handle_command(data):
    """Executes a command dictionary safely."""
    cmd_type = data.get("type")

    try:
        if cmd_type == "click":
            x = data.get("x")
            y = data.get("y")
            button = data.get("button", "left")
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, button=button)
            else:
                pyautogui.click(button=button)
            print(f"✅ Clicked {button} at ({x}, {y})")

        elif cmd_type == "move":
            x = data.get("x")
            y = data.get("y")
            duration = float(data.get("duration", 0.2))
            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=duration)
            print(f"🖱️  Moved to ({x}, {y})")

        elif cmd_type == "type":
            text = data.get("text", "")
            interval = float(data.get("interval", 0.05))
            pyautogui.write(text, interval=interval)
            print(f"⌨️  Typed: {text}")

        else:
            print("⚠️ Unknown command:", cmd_type)
    except pyautogui.FailSafeException:
        print("❌ Action aborted by failsafe (mouse to corner).")


async def connect_relay():
    """Continuously connect to relay and handle messages."""
    while True:
        try:
            print(f"Connecting to relay {RELAY_URL} as PC for pair ID: {PAIR_ID}")
            async with websockets.connect(RELAY_URL) as ws:
                # Register this client
                register_msg = {
                    "type": "register",
                    "role": "pc",
                    "pairId": PAIR_ID,
                    "token": TOKEN
                }
                await ws.send(json.dumps(register_msg))
                print("✅ Registered with relay")

                # Handle messages from relay
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        await handle_command(data)
                    except json.JSONDecodeError:
                        print("⚠️ Received invalid JSON:", msg)
        except Exception as e:
            print(f"⚠️ Relay disconnected ({e}), retrying in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(connect_relay())
