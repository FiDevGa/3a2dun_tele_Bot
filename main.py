import threading
import os
import subprocess
import time
import json
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

@app.route('/')
def home():
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    targets = load_json("connected_channels.json", {})
    last_checked = load_json("last_checked.json", {})
    channel_logs = load_json("channel_logs.json", {})

    total_forwarded = sum(
        len([e for e in entries if e.get("action") == "forwarded"])
        for entries in channel_logs.values()
    )
    total_deleted = sum(
        len([e for e in entries if e.get("action") == "deleted"])
        for entries in channel_logs.values()
    )

    channels_html = ""
    for key, data in targets.items():
        last_id = last_checked.get(key, "—")
        logs = channel_logs.get(key, [])
        last_event = logs[-1] if logs else None
        last_action = f"{last_event['action']} #{last_event['msg_id']} at {last_event['time']}" if last_event else "No activity yet"
        channels_html += f"""
        <div class="channel-card">
            <div class="channel-name">{data['display_name']}</div>
            <div class="channel-meta">@{key}</div>
            <div class="channel-stat">Last post ID: <strong>{last_id}</strong></div>
            <div class="channel-stat">Last event: <span class="tag">{last_action}</span></div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Bot Status</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', sans-serif;
      background: #0f1117;
      color: #e0e0e0;
      min-height: 100vh;
      padding: 40px 20px;
    }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    .header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 36px; }}
    .status-dot {{
      width: 14px; height: 14px; border-radius: 50%;
      background: #2ecc71; box-shadow: 0 0 10px #2ecc71;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
    h1 {{ font-size: 1.8rem; font-weight: 700; color: #fff; }}
    .subtitle {{ color: #888; font-size: 0.9rem; margin-top: 2px; }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px; margin-bottom: 36px;
    }}
    .stat-card {{
      background: #1a1d27; border: 1px solid #2a2d3a;
      border-radius: 12px; padding: 20px; text-align: center;
    }}
    .stat-value {{ font-size: 2rem; font-weight: 700; color: #7289da; }}
    .stat-label {{ font-size: 0.8rem; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
    h2 {{ font-size: 1.1rem; color: #aaa; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }}
    .channels-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
    .channel-card {{
      background: #1a1d27; border: 1px solid #2a2d3a;
      border-radius: 10px; padding: 16px;
    }}
    .channel-name {{ font-weight: 600; color: #fff; margin-bottom: 2px; }}
    .channel-meta {{ font-size: 0.8rem; color: #5865f2; margin-bottom: 10px; }}
    .channel-stat {{ font-size: 0.82rem; color: #aaa; margin-top: 4px; }}
    .tag {{ display: inline-block; background: #2a2d3a; border-radius: 4px; padding: 1px 6px; font-size: 0.78rem; color: #ccc; }}
    .footer {{ margin-top: 40px; text-align: center; font-size: 0.8rem; color: #555; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="status-dot"></div>
      <div>
        <h1>Telegram → Discord Bot</h1>
        <div class="subtitle">All systems operational</div>
      </div>
    </div>
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-value">{uptime_str}</div><div class="stat-label">Uptime</div></div>
      <div class="stat-card"><div class="stat-value">{len(targets)}</div><div class="stat-label">Channels Monitored</div></div>
      <div class="stat-card"><div class="stat-value">{total_forwarded}</div><div class="stat-label">Messages Forwarded</div></div>
      <div class="stat-card"><div class="stat-value">{total_deleted}</div><div class="stat-label">Messages Deleted</div></div>
    </div>
    <h2>Monitored Channels</h2>
    <div class="channels-grid">
      {channels_html if channels_html else '<p style="color:#666">No channels connected yet.</p>'}
    </div>
    <div class="footer">
      Last refreshed: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC &nbsp;·&nbsp;
      Ping this page to keep the bot alive
    </div>
  </div>
</body>
</html>"""
    return html


def run_with_restart(name, script):
    """Run a script and automatically restart it if it crashes."""
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
    # Start Flask in a background thread
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    time.sleep(2)

    # Start bot and monitor — each will auto-restart on crash
    bot_thread = threading.Thread(target=run_with_restart, args=("Discord Bot", "bot.py"), daemon=True)
    monitor_thread = threading.Thread(target=run_with_restart, args=("Telegram Monitor", "monitor.py"), daemon=True)

    bot_thread.start()
    monitor_thread.start()

    # Keep main thread alive forever
    while True:
        time.sleep(60)
