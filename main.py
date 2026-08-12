import threading
import os
import subprocess
import time
import json
import requests
from datetime import datetime
from aiohttp import web
import asyncio
from flask import Flask

START_TIME = time.time()

# ─────────────────────────────────────────────
# Flask Web Server (Keep-Alive)
# ─────────────────────────────────────────────

app = Flask(__name__)


@app.route("/")
def home():
    return "🤖 Bot is alive and running!"


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)


def keep_alive():
    """Run the web server in a background thread"""
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print(f"🌐 Web server started on port {os.environ.get('PORT', 8080)}")

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
    # Start the web server thread first (keep-alive)
    keep_alive()
    
    # Start bot and monitor threads
    bot_thread     = threading.Thread(target=run_with_restart, args=("Discord Bot", "bot.py"), daemon=True)
    monitor_thread = threading.Thread(target=run_with_restart, args=("Telegram Monitor", "monitor.py"), daemon=True)
    
    bot_thread.start()
    monitor_thread.start()
    
    print("🚀 Discord Bot and Telegram Monitor started.")

    while True:
        time.sleep(60)
