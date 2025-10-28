# pc_agent_ai.py
import asyncio
import json
import logging
import re
import subprocess
import os
import pyautogui
import websockets
import urllib.parse
import argparse
from typing import Any, Dict, List, Tuple
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pc_agent')

pyautogui.FAILSAFE = True

# ==========================================================
# Configuration
# ==========================================================
RELAY_URL = os.environ.get('RELAY_URL', 'wss://phone-controller-1.onrender.com')
TOKEN = os.environ.get('PC_AGENT_TOKEN', 'helloworld')

# ==========================================================
# Safe Command Mapping
# ==========================================================

class CommandMapper:
    """Maps natural language to safe, approved actions"""
    
    def __init__(self):
        # Approved applications that can be opened
        self.approved_apps = {
            'chrome': 'chrome',
            'google chrome': 'chrome',
            'browser': 'chrome',
            'notepad': 'notepad',
            'calculator': 'calc',
            'paint': 'mspaint',
            'file explorer': 'explorer',
            'word': 'winword',
            'excel': 'excel',
            'powerpoint': 'powerpnt',
            'vs code': 'code',
            'visual studio code': 'code',
            'command prompt': 'cmd',
            'terminal': 'cmd',
            'task manager': 'taskmgr',
            'control panel': 'control',
        }
        
        # Approved system commands
        self.approved_commands = {
            'shutdown': 'shutdown /s /t 0',
            'restart': 'shutdown /r /t 0',
            'lock': 'rundll32.exe user32.dll,LockWorkStation',
            'sleep': 'rundll32.exe powrprof.dll,SetSuspendState 0,1,0',
        }
        
        # Mouse and keyboard patterns
        self.mouse_patterns = {
            r'click(?:\s+(?:left|right|middle))?': 'click',
            r'right click': 'right_click',
            r'double click': 'double_click',
            r'scroll (up|down)': 'scroll',
            r'move mouse (?:to )?(\d+)[, ]\s*(\d+)': 'move_to',
        }
        
        # Keyboard patterns
        self.keyboard_patterns = {
            r'type (.+)': 'type_text',
            r'press (enter|space|tab|escape|esc|backspace|delete|up|down|left|right)': 'press_key',
            r'hotkey (ctrl|ctrl\+|alt|alt\+|shift|shift\+|win|win\+)(.+)': 'hotkey',
        }

    def sanitize_input(self, text: str) -> str:
        """Remove potentially dangerous characters"""
        # Remove command injection characters
        sanitized = re.sub(r'[;&|`$]', '', text)
        return sanitized.strip()

    def parse_command(self, text: str) -> Dict[str, Any]:
        """Parse natural language and return action command"""
        text = self.sanitize_input(text.lower())
        logger.info(f"Parsing command: '{text}'")
        
        # Check for application launch
        for app_name, app_cmd in self.approved_apps.items():
            if app_name in text:
                return {
                    'type': 'launch_app',
                    'app': app_cmd,
                    'original_text': text,
                    'confidence': 0.9
                }
        
        # Check for system commands
        for cmd_name, cmd in self.approved_commands.items():
            if cmd_name in text:
                return {
                    'type': 'system_command',
                    'command': cmd,
                    'original_text': text,
                    'confidence': 0.9
                }
        
        # Check mouse patterns
        for pattern, action in self.mouse_patterns.items():
            match = re.search(pattern, text)
            if match:
                if action == 'move_to':
                    x, y = int(match.group(1)), int(match.group(2))
                    return {
                        'type': 'move',
                        'x': x, 'y': y,
                        'original_text': text,
                        'confidence': 0.8
                    }
                elif action == 'click':
                    return {
                        'type': 'click',
                        'button': 'left',
                        'original_text': text,
                        'confidence': 0.8
                    }
                elif action == 'right_click':
                    return {
                        'type': 'click',
                        'button': 'right', 
                        'original_text': text,
                        'confidence': 0.8
                    }
                elif action == 'double_click':
                    return {
                        'type': 'double_click',
                        'original_text': text,
                        'confidence': 0.8
                    }
                elif action == 'scroll':
                    direction = match.group(1)
                    return {
                        'type': 'scroll',
                        'direction': direction,
                        'original_text': text,
                        'confidence': 0.7
                    }
        
        # Check keyboard patterns
        for pattern, action in self.keyboard_patterns.items():
            match = re.search(pattern, text)
            if match:
                if action == 'type_text':
                    text_to_type = match.group(1)
                    return {
                        'type': 'type',
                        'text': text_to_type,
                        'original_text': text,
                        'confidence': 0.8
                    }
                elif action == 'press_key':
                    key = match.group(1)
                    key_map = {
                        'enter': 'enter', 'space': 'space', 'tab': 'tab',
                        'escape': 'escape', 'esc': 'escape', 'backspace': 'backspace',
                        'delete': 'delete', 'up': 'up', 'down': 'down',
                        'left': 'left', 'right': 'right'
                    }
                    return {
                        'type': 'press_key',
                        'key': key_map.get(key, key),
                        'original_text': text,
                        'confidence': 0.8
                    }
        
        # Default: treat as typing if no other pattern matches
        return {
            'type': 'type',
            'text': text,
            'original_text': text,
            'confidence': 0.3
        }

# ==========================================================
# Enhanced Command Handlers
# ==========================================================

command_mapper = CommandMapper()

async def handle_launch_app(payload: Dict[str, Any]):
    """Safely launch approved applications"""
    app = payload.get('app')
    if app in command_mapper.approved_apps.values():
        try:
            logger.info(f'Launching application: {app}')
            if os.name == 'nt':  # Windows
                subprocess.Popen(app, shell=True)
            else:  # macOS/Linux
                subprocess.Popen([app])
            return {'ok': True, 'message': f'Launched {app}'}
        except Exception as e:
            logger.error(f'Failed to launch {app}: {e}')
            return {'ok': False, 'error': f'Failed to launch {app}'}
    else:
        return {'ok': False, 'error': 'Application not approved'}

async def handle_system_command(payload: Dict[str, Any]):
    """Execute approved system commands"""
    command = payload.get('command')
    if command in command_mapper.approved_commands.values():
        try:
            logger.info(f'Executing system command: {command}')
            subprocess.run(command, shell=True, timeout=5)
            return {'ok': True, 'message': 'Command executed'}
        except subprocess.TimeoutExpired:
            logger.warning('Command timed out')
            return {'ok': True, 'message': 'Command initiated'}
        except Exception as e:
            logger.error(f'Command failed: {e}')
            return {'ok': False, 'error': 'Command failed'}
    else:
        return {'ok': False, 'error': 'Command not approved'}

async def handle_double_click(payload: Dict[str, Any]):
    """Handle double click"""
    try:
        pyautogui.doubleClick()
        logger.info('Double click performed')
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_scroll(payload: Dict[str, Any]):
    """Handle mouse scroll"""
    direction = payload.get('direction', 'down')
    clicks = -100 if direction == 'down' else 100
    try:
        pyautogui.scroll(clicks)
        logger.info(f'Scrolled {direction}')
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_press_key(payload: Dict[str, Any]):
    """Press a single key"""
    key = payload.get('key')
    try:
        pyautogui.press(key)
        logger.info(f'Pressed key: {key}')
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_ai_command(payload: Dict[str, Any]):
    """Handle natural language commands"""
    text = payload.get('text', '')
    if not text:
        return {'ok': False, 'error': 'No text provided'}
    
    # Parse the natural language command
    parsed_command = command_mapper.parse_command(text)
    logger.info(f"Parsed command: {parsed_command}")
    
    # Execute the parsed command
    command_type = parsed_command['type']
    if command_type in ENHANCED_HANDLERS:
        result = await ENHANCED_HANDLERS[command_type](parsed_command)
        result['parsed_command'] = parsed_command
        return result
    else:
        return {'ok': False, 'error': f'Unknown command type: {command_type}'}

# Original handlers (updated to return results)
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
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_type(payload: Dict[str, Any]):
    text = payload.get('text', '')
    interval = float(payload.get('interval', 0.05))
    logger.info('Typing text: %s', text)
    try:
        pyautogui.write(text, interval=interval)
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_move(payload: Dict[str, Any]):
    x = payload.get('x')
    y = payload.get('y')
    duration = float(payload.get('duration', 0.1))
    logger.info('Moving mouse to x=%s y=%s duration=%s', x, y, duration)
    try:
        if x is not None and y is not None:
            pyautogui.moveTo(x, y, duration=duration)
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

# Enhanced command handlers
ENHANCED_HANDLERS = {
    'click': handle_click,
    'type': handle_type,
    'move': handle_move,
    'launch_app': handle_launch_app,
    'system_command': handle_system_command,
    'double_click': handle_double_click,
    'scroll': handle_scroll,
    'press_key': handle_press_key,
    'ai_command': handle_ai_command,
}

# ==========================================================
# Relay Connection (same as before)
# ==========================================================

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
        
        # Handle authentication messages
        if data.get('type') == 'auth':
            logger.info('🔐 Auth request received')
            response = {'ok': True, 'auth': True, 'type': 'auth_response'}
            await websocket.send(json.dumps(response))
            return
            
        # Process commands
        cmd_type = data.get('type')
        if cmd_type in ENHANCED_HANDLERS:
            result = await ENHANCED_HANDLERS[cmd_type](data)
            await websocket.send(json.dumps(result))
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
        websocket = await websockets.connect(ws_url, ping_interval=20, ping_timeout=10)
        logger.info('✅ Connected to relay server as PC client')
        
        await websocket.send(json.dumps({'type': 'auth', 'token': TOKEN}))
        
        async for message in websocket:
            await handle_relay_message(websocket, message)
            
    except websockets.exceptions.ConnectionClosed:
        logger.warning('🔌 Connection closed by relay')
    except Exception as e:
        logger.error('❌ Connection error: %s', e)
    finally:
        if 'websocket' in locals():
            await websocket.close()
        logger.info('🔌 Disconnected from relay')

async def main():
    logger.info('🚀 Starting PC Agent (AI Control Layer)')
    logger.info('🔑 Token: %s', TOKEN)
    logger.info('🌐 Relay URL: %s', RELAY_URL)
    logger.info('🤖 Available commands: %s', list(ENHANCED_HANDLERS.keys()))
    
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