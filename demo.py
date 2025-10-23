"""
Safe demo script for controlling the PC with pyautogui.

Behavior:
- Waits 5 seconds to give you a chance to switch away/cancel.
- Shows a short countdown in the console.
- Moves the mouse slightly and types a short message.
- Provides instructions for a safe abort (move mouse to top-left corner to raise FailSafe).

Run this in a virtualenv. Do NOT run with elevated privileges unnecessarily.
"""
import time
import pyautogui

# PyAutoGUI failsafe: move mouse to top-left corner to immediately raise exception
pyautogui.FAILSAFE = True

def countdown(seconds: int):
    for i in range(seconds, 0, -1):
        print(f"Starting in {i}... (move mouse to top-left corner to abort)")
        time.sleep(1)


def demo_actions():
    # A gentle, non-destructive demo: small mouse move and typing
    print("Running demo actions: moving mouse slightly and typing 'Hello from PC'")

    # Record the current mouse position and restore later
    x, y = pyautogui.position()
    try:
        # Move mouse by 50 pixels to the right and back
        pyautogui.moveTo(x + 50, y, duration=0.5)
        pyautogui.moveTo(x, y, duration=0.5)

        # Type a short message
        pyautogui.write('Hello from PC', interval=0.05)
        pyautogui.press('enter')
    except pyautogui.FailSafeException:
        print('Demo aborted by moving mouse to top-left corner (failsafe).')


if __name__ == '__main__':
    countdown(5)
    demo_actions()
    print('Demo complete.')
