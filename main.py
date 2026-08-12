import threading
import os
import subprocess
import time
import json
import requests
from flask import Flask
from datetime import datetime

app = Flask('')
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

@app.route('/ping')
def ping():
    return "pong", 200


def self_ping():
    """Ping ourselves every 30 seconds to stay alive on autoscale deployments."""
    time.sleep(15)
    while True:
        try:
            requests.get("http://127.0.0.1:5000/ping", timeout=10)
        except Exception:
            pass
        time.sleep(30)


def run_with_restart(name, script):
    while True:
        print(f"▶️  Starting {name}...")
        try:
            subprocess.run(["python", script])
        except Exception as e:
            print(f"❌ {name} raised an exception: {e}")
        print(f"🔁 {name} exited — restarting in 5 seconds...")
        time.sleep(5)


def run_web_server():
    app.run(host='0.0.0.0', port=5000)


if __name__ == "__main__":
    IS_DEPLOYED = os.environ.get('REPLIT_DEPLOYMENT', '0') == '1'

    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    time.sleep(2)

    if IS_DEPLOYED:
        # Only run bot + monitor in the deployed environment.
        # Both running in dev causes duplicate command responses and double message forwarding.
        bot_thread     = threading.Thread(target=run_with_restart, args=("Discord Bot", "bot.py"), daemon=True)
        ping_thread    = threading.Thread(target=self_ping, daemon=True)
        monitor_thread = threading.Thread(target=run_with_restart, args=("Telegram Monitor", "monitor.py"), daemon=True)
        bot_thread.start()
        ping_thread.start()
        monitor_thread.start()
        print("🚀 Deployed mode — bot + monitor + self-ping started.")
    else:
        print("🛠️  Dev mode — bot + monitor DISABLED (prevents duplicate commands & forwarding).")
        print("🛠️  Status page is available here for monitoring.")

    while True:
        time.sleep(60)
