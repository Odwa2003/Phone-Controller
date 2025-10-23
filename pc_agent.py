"""
PC Agent (Relay Version) - UPDATED
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
import sys
import pyautogui
import websockets

# Configure pyautogui for safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05  # Small delay between actions

RELAY_URL = os.environ.get("RELAY_URL", "wss://phone-controller-s2pe.onrender.com")
PAIR_ID = os.environ.get("PAIR_ID", "pair123")
TOKEN = os.environ.get("PC_TOKEN", "my-secret-token")

def get_screen_size():
    """Get the current screen size."""
    try:
        width, height = pyautogui.size()
        return width, height
    except Exception as e:
        print(f"❌ Could not get screen size: {e}")
        return 1920, 1080  # Default fallback

SCREEN_WIDTH, SCREEN_HEIGHT = get_screen_size()
print(f"🖥️  Screen size: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")

async def handle_command(data):
    """Executes a command dictionary safely."""
    print(f"🔧 Received command: {data}")
    cmd_type = data.get("type")

    try:
        if cmd_type == "click":
            x = data.get("x")
            y = data.get("y")
            button = data.get("button", "left")
            
            # Validate coordinates
            if x is not None and y is not None:
                if x < 0 or y < 0 or x > SCREEN_WIDTH or y > SCREEN_HEIGHT:
                    print(f"⚠️ Coordinates out of bounds: ({x}, {y})")
                    return
                print(f"🖱️ Attempting click at ({x}, {y}) with {button} button")
                pyautogui.click(x=x, y=y, button=button)
            else:
                print(f"🖱️ Attempting click at current position with {button} button")
                pyautogui.click(button=button)
            print(f"✅ Clicked {button} at ({x}, {y})")

        elif cmd_type == "move":
            x = data.get("x")
            y = data.get("y")
            duration = float(data.get("duration", 0.2))
            
            if x is not None and y is not None:
                # Validate coordinates
                if x < 0 or y < 0 or x > SCREEN_WIDTH or y > SCREEN_HEIGHT:
                    print(f"⚠️ Coordinates out of bounds: ({x}, {y})")
                    return
                print(f"🎯 Moving to ({x}, {y}) over {duration}s")
                pyautogui.moveTo(x, y, duration=duration)
                print(f"✅ Moved to ({x}, {y})")
            else:
                print("⚠️ Missing coordinates for move command")

        elif cmd_type == "type":
            text = data.get("text", "")
            interval = float(data.get("interval", 0.05))
            
            if text:
                print(f"⌨️  Typing: '{text}'")
                pyautogui.write(text, interval=interval)
                print(f"✅ Typed: '{text}'")
            else:
                print("⚠️ Empty text for type command")

        elif cmd_type == "scroll":
            clicks = data.get("clicks", 1)
            print(f"📜 Scrolling {clicks} clicks")
            pyautogui.scroll(clicks)
            print(f"✅ Scrolled {clicks} clicks")

        elif cmd_type == "key":
            key = data.get("key")
            if key:
                print(f"⌨️  Pressing key: {key}")
                pyautogui.press(key)
                print(f"✅ Pressed key: {key}")
            else:
                print("⚠️ Missing key for key command")

        elif cmd_type == "hotkey":
            keys = data.get("keys", [])
            if keys:
                print(f"🔗 Pressing hotkey: {keys}")
                pyautogui.hotkey(*keys)
                print(f"✅ Pressed hotkey: {keys}")
            else:
                print("⚠️ Missing keys for hotkey command")

        elif cmd_type == "partner_connected":
            print("🎉 Phone connected to relay!")
            
        elif cmd_type == "partner_disconnected":
            print("📱 Phone disconnected from relay!")

        else:
            print(f"⚠️ Unknown command type: {cmd_type}")

    except pyautogui.FailSafeException:
        print("❌ Action aborted by failsafe (mouse moved to corner)")
    except Exception as e:
        print(f"❌ Error executing command {cmd_type}: {e}")

async def connect_relay():
    """Continuously connect to relay and handle messages."""
    reconnect_delay = 5
    max_reconnect_delay = 60
    
    while True:
        try:
            print(f"🔗 Connecting to relay: {RELAY_URL}")
            print(f"📋 Pair ID: {PAIR_ID}")
            print(f"🔑 Token: {'*' * len(TOKEN) if TOKEN else 'None'}")
            
            async with websockets.connect(
                RELAY_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ) as ws:
                # Register this client
                register_msg = {
                    "type": "register",
                    "role": "pc",
                    "pairId": PAIR_ID,
                    "token": TOKEN
                }
                await ws.send(json.dumps(register_msg))
                print("✅ Registered with relay as PC")
                reconnect_delay = 5  # Reset reconnect delay on successful connection

                # Handle messages from relay
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        print(f"📨 Received: {data}")
                        
                        # Handle system messages
                        if data.get('type') in ['partner_connected', 'partner_disconnected']:
                            await handle_command(data)
                        elif data.get('ok') is not None:
                            # Registration response or other system message
                            print(f"📢 System: {data}")
                        else:
                            # Actual command to execute
                            await handle_command(data)
                            
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Received invalid JSON: {msg}")
                        print(f"Error: {e}")
                    except Exception as e:
                        print(f"⚠️ Error processing message: {e}")
                        
        except websockets.exceptions.ConnectionClosed as e:
            print(f"🔌 Connection closed: {e}")
            print(f"🔄 Reconnecting in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
            
        except websockets.exceptions.WebSocketException as e:
            print(f"🌐 WebSocket error: {e}")
            print(f"🔄 Reconnecting in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
            
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            print(f"🔄 Reconnecting in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)

def main():
    """Main entry point with proper signal handling."""
    print("🚀 Starting PC Agent...")
    print("=" * 50)
    print(f"🖥️  Screen size: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    print(f"🔗 Relay URL: {RELAY_URL}")
    print(f"📋 Pair ID: {PAIR_ID}")
    print(f"🔐 Token: {'*' * len(TOKEN) if TOKEN else 'None'}")
    print("=" * 50)
    print("Press Ctrl+C to stop")
    print()
    
    try:
        asyncio.run(connect_relay())
    except KeyboardInterrupt:
        print("\n👋 Shutting down PC Agent...")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()