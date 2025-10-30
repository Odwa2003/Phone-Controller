# pc_agent_ai_nlp.py
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
import openai
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pc_agent')

pyautogui.FAILSAFE = True

# ==========================================================
# Configuration
# ==========================================================
RELAY_URL = os.environ.get('RELAY_URL', 'wss://phone-controller-1.onrender.com')
TOKEN = os.environ.get('PC_AGENT_TOKEN', 'helloworld')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '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')

# ==========================================================
# AI/NLP Layer with OpenAI
# ==========================================================

class AINLPProcessor:
    """Uses OpenAI API to convert natural language to structured commands"""
    
    def __init__(self, api_key: str):
        if api_key:
            openai.api_key = api_key
            self.enabled = True
        else:
            self.enabled = False
            logger.warning("OpenAI API key not provided. AI/NLP layer disabled.")
        
        # Fallback pattern matcher for when AI is unavailable
        self.pattern_matcher = PatternMatcher()
        
        # System prompt for the AI
        self.system_prompt = """You are a PC control assistant that converts natural language commands into structured JSON actions.

Available actions:
- open_app: Open applications (chrome, notepad, calculator, etc.)
- navigate_url: Open specific websites in browser
- mouse_click: Click at coordinates or current position
- mouse_move: Move mouse to coordinates
- mouse_scroll: Scroll up/down
- keyboard_type: Type text
- keyboard_press: Press specific keys
- system_command: Lock, sleep, shutdown, restart

Always respond with valid JSON only, no other text.

Example conversions:
User: "Can you open YouTube?"
Output: {"intent": "navigate_url", "target": "youtube.com"}

User: "Please click at position 100,200"
Output: {"intent": "mouse_click", "x": 100, "y": 200}

User: "Type hello world and press enter"
Output: {"intent": "keyboard_type", "text": "hello world", "then_press": "enter"}

User: "Move mouse to the center and right click"
Output: {"intent": "mouse_move", "x": 960, "y": 540}, {"intent": "mouse_click", "button": "right"}

User: "Open Chrome and go to google"
Output: [{"intent": "open_app", "target": "chrome"}, {"intent": "navigate_url", "target": "google.com"}]

User: "Lock my computer"
Output: {"intent": "system_command", "action": "lock"}"""

    async def process_command(self, text: str) -> List[Dict[str, Any]]:
        """Convert natural language to structured commands using AI"""
        if not self.enabled:
            logger.info("AI/NLP disabled, using pattern matching fallback")
            return self.pattern_matcher.parse_command(text)
        
        try:
            logger.info(f"🤖 Processing AI command: '{text}'")
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"AI Raw Response: {ai_response}")
            
            # Parse JSON response
            commands = self._parse_ai_response(ai_response)
            logger.info(f"Parsed AI Commands: {commands}")
            
            return commands
            
        except Exception as e:
            logger.error(f"AI processing failed: {e}. Using fallback pattern matching.")
            return self.pattern_matcher.parse_command(text)
    
    def _parse_ai_response(self, ai_response: str) -> List[Dict[str, Any]]:
        """Parse AI response into command list"""
        try:
            # Clean the response (remove markdown code blocks if present)
            cleaned_response = re.sub(r'```json\n?|\n?```', '', ai_response).strip()
            
            # Try to parse as single command or array of commands
            if cleaned_response.startswith('['):
                commands = json.loads(cleaned_response)
            else:
                commands = [json.loads(cleaned_response)]
            
            # Add metadata
            for cmd in commands:
                cmd['ai_processed'] = True
                cmd['confidence'] = 0.95
                
            return commands
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI JSON response: {e}")
            return [{
                'intent': 'keyboard_type',
                'text': f"Error: Could not understand command. AI said: {ai_response}",
                'ai_processed': False,
                'confidence': 0.0
            }]

class PatternMatcher:
    """Fallback pattern matcher when AI is unavailable"""
    
    def __init__(self):
        self.approved_apps = {
            'chrome': 'chrome', 'browser': 'chrome', 'google chrome': 'chrome',
            'notepad': 'notepad', 'calculator': 'calc', 'paint': 'mspaint',
            'file explorer': 'explorer', 'explorer': 'explorer', 'files': 'explorer',
            'word': 'winword', 'excel': 'excel', 'powerpoint': 'powerpnt',
            'vs code': 'code', 'code': 'code', 'command prompt': 'cmd',
            'terminal': 'cmd', 'task manager': 'taskmgr', 'control panel': 'control',
            'mail': 'outlookmail:',
        }
        
        self.websites = {
            'youtube': 'youtube.com', 'google': 'google.com', 'github': 'github.com',
            'facebook': 'facebook.com', 'twitter': 'twitter.com', 'reddit': 'reddit.com',
            'gmail': 'gmail.com', 'outlook': 'outlook.com', 'amazon': 'amazon.com',
            'render': 'render.com',
        }

    def parse_command(self, text: str) -> List[Dict[str, Any]]:
        """Fallback pattern-based command parsing"""
        text = text.lower().strip()
        commands = []
        
        # Check for app opening
        for app_name, app_cmd in self.approved_apps.items():
            if app_name in text:
                commands.append({
                    'intent': 'open_app',
                    'target': app_cmd,
                    'original_text': text,
                    'ai_processed': False,
                    'confidence': 0.7
                })
                return commands
        
        # Check for website navigation
        for site_name, site_url in self.websites.items():
            if site_name in text:
                commands.append({
                    'intent': 'navigate_url', 
                    'target': site_url,
                    'original_text': text,
                    'ai_processed': False,
                    'confidence': 0.7
                })
                return commands
        
        # Check for coordinates
        coord_match = re.search(r'(\d+)[, ]\s*(\d+)', text)
        if coord_match and ('click' in text or 'move' in text):
            x, y = int(coord_match.group(1)), int(coord_match.group(2))
            if 'click' in text:
                button = 'right' if 'right' in text else 'left'
                commands.append({
                    'intent': 'mouse_click',
                    'x': x, 'y': y,
                    'button': button,
                    'original_text': text,
                    'ai_processed': False,
                    'confidence': 0.8
                })
            else:
                commands.append({
                    'intent': 'mouse_move',
                    'x': x, 'y': y,
                    'original_text': text,
                    'ai_processed': False,
                    'confidence': 0.8
                })
            return commands
        
        # Default to typing
        commands.append({
            'intent': 'keyboard_type',
            'text': text,
            'original_text': text,
            'ai_processed': False,
            'confidence': 0.3
        })
        
        return commands

# ==========================================================
# Enhanced Command Handlers
# ==========================================================

ai_processor = AINLPProcessor(OPENAI_API_KEY)

async def handle_open_app(payload: Dict[str, Any]):
    """Open approved applications"""
    app = payload.get('target')
    approved_apps = ai_processor.pattern_matcher.approved_apps
    if app in approved_apps.values():
        try:
            logger.info(f'🚀 Launching application: {app}')
            if os.name == 'nt':  # Windows
                subprocess.Popen("start " + app, shell=True)
            else:  # macOS/Linux
                subprocess.Popen([app])
            return {'ok': True, 'message': f'Launched {app}'}
        except Exception as e:
            logger.error(f'Failed to launch {app}: {e}')
            return {'ok': False, 'error': f'Failed to launch {app}'}
    else:
        return {'ok': False, 'error': 'Application not approved'}

async def handle_navigate_url(payload: Dict[str, Any]):
    """Navigate to website in browser"""
    url = payload.get('target')
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    
    try:
        logger.info(f'🌐 Navigating to: {url}')
        # Try to use default browser
        if os.name == 'nt':  # Windows
            subprocess.Popen(f'start {url}', shell=True)
        else:  # macOS/Linux
            subprocess.Popen(['xdg-open', url])  # Linux
        return {'ok': True, 'message': f'Opened {url}'}
    except Exception as e:
        logger.error(f'Failed to open URL: {e}')
        return {'ok': False, 'error': f'Failed to open {url}'}

async def handle_mouse_click(payload: Dict[str, Any]):
    """Handle mouse clicks"""
    x = payload.get('x')
    y = payload.get('y')
    button = payload.get('button', 'left')
    
    try:
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, button=button)
            logger.info(f'🖱️ Clicked at ({x}, {y}) with {button} button')
        else:
            pyautogui.click(button=button)
            logger.info(f'🖱️ Clicked at current position with {button} button')
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_mouse_move(payload: Dict[str, Any]):
    """Handle mouse movement"""
    x = payload.get('x')
    y = payload.get('y')
    duration = payload.get('duration', 0.5)
    
    try:
        if x is not None and y is not None:
            pyautogui.moveTo(x, y, duration=duration)
            logger.info(f'🖱️ Moved mouse to ({x}, {y})')
            return {'ok': True}
        else:
            return {'ok': False, 'error': 'Missing coordinates'}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_mouse_scroll(payload: Dict[str, Any]):
    """Handle mouse scrolling"""
    direction = payload.get('direction', 'down')
    clicks = payload.get('clicks', 3)
    scroll_amount = -clicks if direction == 'down' else clicks
    
    try:
        pyautogui.scroll(scroll_amount)
        logger.info(f'📜 Scrolled {direction}')
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_keyboard_type(payload: Dict[str, Any]):
    """Handle keyboard typing"""
    text = payload.get('text', '')
    then_press = payload.get('then_press')
    
    try:
        pyautogui.write(text)
        logger.info(f'⌨️ Typed: {text}')
        
        if then_press:
            pyautogui.press(then_press)
            logger.info(f'⌨️ Pressed: {then_press}')
            
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_keyboard_press(payload: Dict[str, Any]):
    """Handle key presses"""
    key = payload.get('key')
    try:
        pyautogui.press(key)
        logger.info(f'⌨️ Pressed key: {key}')
        return {'ok': True}
    except pyautogui.FailSafeException:
        logger.warning('Action aborted by failsafe.')
        return {'ok': False, 'error': 'Failsafe triggered'}

async def handle_system_command(payload: Dict[str, Any]):
    """Handle system commands"""
    action = payload.get('action')
    commands = {
        'lock': 'rundll32.exe user32.dll,LockWorkStation',
        'sleep': 'rundll32.exe powrprof.dll,SetSuspendState 0,1,0',
        'shutdown': 'shutdown /s /t 0',
        'restart': 'shutdown /r /t 0',
    }
    
    if action in commands:
        try:
            logger.info(f'⚙️ Executing system command: {action}')
            subprocess.run(commands[action], shell=True, timeout=5)
            return {'ok': True, 'message': f'Executed {action}'}
        except Exception as e:
            logger.error(f'System command failed: {e}')
            return {'ok': False, 'error': f'Failed to {action}'}
    else:
        return {'ok': False, 'error': f'Unknown system action: {action}'}

async def handle_ai_command(payload: Dict[str, Any]):
    """Handle natural language commands using AI"""
    text = payload.get('text', '')
    if not text:
        return {'ok': False, 'error': 'No text provided'}
    
    try:
        # Process with AI
        ai_commands = await ai_processor.process_command(text)
        logger.info(f"🤖 AI generated {len(ai_commands)} command(s)")
        
        # Execute all commands in sequence
        results = []
        for i, cmd in enumerate(ai_commands):
            logger.info(f"Executing command {i+1}: {cmd}")
            intent = cmd.get('intent')
            if intent in AI_HANDLERS:
                result = await AI_HANDLERS[intent](cmd)
                results.append(result)
                
                # Small delay between commands
                if i < len(ai_commands) - 1:
                    await asyncio.sleep(0.5)
            else:
                results.append({'ok': False, 'error': f'Unknown intent: {intent}'})
        
        return {
            'ok': all(r.get('ok', False) for r in results),
            'results': results,
            'ai_commands': ai_commands,
            'command_count': len(ai_commands)
        }
        
    except Exception as e:
        logger.error(f'AI command processing failed: {e}')
        return {'ok': False, 'error': str(e)}

# AI Intent Handlers
AI_HANDLERS = {
    'open_app': handle_open_app,
    'navigate_url': handle_navigate_url,
    'mouse_click': handle_mouse_click,
    'mouse_move': handle_mouse_move,
    'mouse_scroll': handle_mouse_scroll,
    'keyboard_type': handle_keyboard_type,
    'keyboard_press': handle_keyboard_press,
    'system_command': handle_system_command,
}

# Original handlers (for backward compatibility)
async def handle_click(payload: Dict[str, Any]):
    return await handle_mouse_click(payload)

async def handle_type(payload: Dict[str, Any]):
    return await handle_keyboard_type(payload)

async def handle_move(payload: Dict[str, Any]):
    return await handle_mouse_move(payload)

async def handle_system_direct(payload: Dict[str, Any]):
    return await handle_system_command(payload)

# Combined handlers
ENHANCED_HANDLERS = {
    **AI_HANDLERS,
    'click': handle_click,
    'type': handle_type,
    'move': handle_move,
    'system_command': handle_system_direct,
    'ai_command': handle_ai_command,
}

# ==========================================================
# Relay Connection (same structure)
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
        logger.info('✅ Connected to relay server as PC agent')
        
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
    logger.info('🚀 Starting PC Agent (AI/NLP Enhanced)')
    logger.info('🔑 Token: %s', TOKEN)
    logger.info('🌐 Relay URL: %s', RELAY_URL)
    logger.info('🤖 AI Enabled: %s', ai_processor.enabled)
    logger.info('🎯 Available intents: %s', list(AI_HANDLERS.keys()))
    
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
    parser = argparse.ArgumentParser(description='PC Agent with AI/NLP Control Layer')
    parser.add_argument('--relay-url', help='Relay server URL')
    parser.add_argument('--token', help='Authentication token')
    parser.add_argument('--openai-key', help='OpenAI API key')
    args = parser.parse_args()
    
    if args.relay_url:
        RELAY_URL = args.relay_url
    if args.token:
        TOKEN = args.token
    if args.openai_key:
        OPENAI_API_KEY = args.openai_key
        ai_processor = AINLPProcessor(OPENAI_API_KEY)
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('👋 Shutting down...')