Phone-Controller — Step 1: PC control basics

This small demo shows how to automate keyboard/mouse actions on your PC using Python and pyautogui.

Setup

1. Install Python 3.8+ from https://www.python.org/ and ensure `python` and `pip` are on your PATH.
2. Create a virtual environment (recommended):

   python -m venv .venv
   .\.venv\Scripts\Activate.ps1  # PowerShell

3. Install dependencies:

   pip install -r requirements.txt

Run the demo

   python demo.py

Safety notes

- PyAutoGUI has a failsafe feature: move the mouse to the top-left corner of the screen to raise an exception and stop automated actions.
- The demo waits 5 seconds before acting so you can switch focus or cancel.
- Do not run automation scripts that type or click with elevated privileges unless you understand the risks.

Next steps

- We'll add a websockets-based server so your phone can send commands to this script. We'll plan authentication and rate-limiting to keep it safe.
