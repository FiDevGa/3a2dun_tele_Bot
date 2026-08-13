import threading
import os
import subprocess
import time
import json
import requests
from datetime import datetime
from aiohttp import web
import asyncio
from flask import Flask, jsonify
import psutil

START_TIME = time.time()

# Global variables to track process threads
bot_thread = None
monitor_thread = None
processes_started = False

# ─────────────────────────────────────────────
# Flask Web Server (Keep-Alive)
# ─────────────────────────────────────────────

app = Flask(__name__)


@app.route("/")
def home():
    return "🤖 Bot is alive and running!"


@app.route("/ping")
def ping():
    """Check if main.py is running and start it if not"""
    global bot_thread, monitor_thread, processes_started
    
    try:
        # Check if bot.py process is running
        bot_running = check_process_running("bot.py")
        monitor_running = check_process_running("monitor.py")
        
        if bot_running and monitor_running:
            return jsonify({
                "status": "✓ Already running",
                "bot": "Running ✓",
                "monitor": "Running ✓",
                "uptime": f"{time.time() - START_TIME:.0f}s"
            }), 200
        else:
            # Try to restart processes if they're not running
            if not processes_started:
                start_processes()
                return jsonify({
                    "status": "✓ Started main.py",
                    "bot": "Starting...",
                    "monitor": "Starting...",
                    "message": "Processes restarted"
                }), 200
            else:
                return jsonify({
                    "status": "⚠ Processes restarting",
                    "bot": "Running ✓" if bot_running else "Restarting...",
                    "monitor": "Running ✓" if monitor_running else "Restarting...",
                    "uptime": f"{time.time() - START_TIME:.0f}s"
                }), 200
                
    except Exception as e:
        return jsonify({
            "status": "✕ Error checking status",
            "error": str(e)
        }), 500


def check_process_running(script_name):
    """Check if a Python script is running by name"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any(script_name in arg for arg in cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False
    except Exception:
        return False


def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


def keep_alive():
    """Run the web server in a background thread"""
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print(f"🌐 Web server started on port {os.environ.get('PORT', 5000)}")

def start_processes():
    """Start bot and monitor processes"""
    global bot_thread, monitor_thread, processes_started
    
    bot_thread = threading.Thread(target=run_with_restart, args=("Discord Bot", "bot.py"), daemon=True)
    monitor_thread = threading.Thread(target=run_with_restart, args=("Telegram Monitor", "monitor.py"), daemon=True)
    
    bot_thread.start()
    monitor_thread.start()
    processes_started = True
    print("🚀 Discord Bot and Telegram Monitor started.")

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
    start_processes()
    
    print("✅ All services initialized.")

    while True:
        time.sleep(60)