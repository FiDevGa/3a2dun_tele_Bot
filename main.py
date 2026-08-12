import threading
import os
import subprocess
import time
import json
import requests
from datetime import datetime
from aiohttp import web
import asyncio

START_TIME = time.time()

def get_path(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, filename)

def load_json(filename, default):
    path = get_path(filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def run_with_restart(name, script):
    while True:
        print(f"▶️  Starting {name}...")
        try:
            subprocess.run(["python", script])
        except Exception as e:
            print(f"❌ {name} raised an exception: {e}")
        print(f"🔁 {name} exited — restarting in 5 seconds...")
        time.sleep(5)


if __name__ == "__main__":
    # Start bot and monitor threads
    bot_thread     = threading.Thread(target=run_with_restart, args=("Discord Bot", "bot.py"), daemon=True)
    monitor_thread = threading.Thread(target=run_with_restart, args=("Telegram Monitor", "monitor.py"), daemon=True)
    
    bot_thread.start()
    monitor_thread.start()
    
    print("🚀 Discord Bot and Telegram Monitor started.")

    while True:
        time.sleep(60)
