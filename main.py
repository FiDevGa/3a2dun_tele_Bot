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

@app.route('/')
def home():
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    targets = load_json("connected_channels.json", {})
    last_checked = load_json("last_checked.json", {})
    activity_log = load_json("channel_logs.json", [])
    if not isinstance(activity_log, list):
        activity_log = []

    total_forwarded = sum(1 for e in activity_log if e.get("action") == "forwarded")
    total_deleted   = sum(1 for e in activity_log if e.get("action") == "deleted")

    # ── Channel cards ──────────────────────────────────
    channels_html = ""
    for key, data in targets.items():
        last_id = last_checked.get(key, "—")
        recent = next((e for e in activity_log if e.get("channel") == key), None)
        if recent:
            action_icon = "🚀" if recent["action"] == "forwarded" else "🗑️"
            last_action = f'{action_icon} #{recent["msg_id"]} &nbsp;·&nbsp; {recent["time"]}'
        else:
            last_action = "No activity yet"

        channels_html += f"""
        <div class="channel-card">
          <div class="channel-name">{data['display_name']}</div>
          <div class="channel-meta">@{key}</div>
          <div class="channel-stat">Last post ID: <strong>{last_id}</strong></div>
          <div class="channel-stat last-event">{last_action}</div>
        </div>"""

    # ── Recent activity feed (last 30) ─────────────────
    feed_html = ""
    for entry in activity_log[:30]:
        is_fwd = entry.get("action") == "forwarded"
        icon     = "🚀" if is_fwd else "🗑️"
        color    = "#2ecc71" if is_fwd else "#e74c3c"
        label    = "Forwarded" if is_fwd else "Deleted"
        ch       = entry.get("display_name", entry.get("channel", "?"))
        msg_id   = entry.get("msg_id", "?")
        tg_link  = entry.get("tg_link")
        ts       = entry.get("time", "")
        id_part  = f'<a href="{tg_link}" target="_blank" style="color:#7289da">#{msg_id}</a>' if tg_link else f"#{msg_id}"
        feed_html += f"""
        <div class="feed-row">
          <span class="feed-badge" style="background:{color}22;color:{color}">{icon} {label}</span>
          <span class="feed-ch">{ch}</span>
          <span class="feed-id">{id_part}</span>
          <span class="feed-time">{ts}</span>
        </div>"""

    if not feed_html:
        feed_html = '<div style="color:#555;padding:16px 0">No messages forwarded yet — the bot is watching.</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta http-equiv="refresh" content="30"/>
  <title>Telegram → Discord Bot</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e0e0e0;min-height:100vh;padding:36px 20px}}
    a{{text-decoration:none}}
    .container{{max-width:960px;margin:0 auto}}

    /* header */
    .header{{display:flex;align-items:center;gap:14px;margin-bottom:32px}}
    .dot{{width:13px;height:13px;border-radius:50%;background:#2ecc71;box-shadow:0 0 10px #2ecc71;animation:pulse 2s infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
    h1{{font-size:1.7rem;font-weight:700;color:#fff}}
    .sub{{color:#666;font-size:.85rem;margin-top:3px}}

    /* stat cards */
    .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:36px}}
    .stat{{background:#1a1d27;border:1px solid #2a2d3a;border-radius:12px;padding:18px;text-align:center}}
    .stat-val{{font-size:1.9rem;font-weight:700;color:#7289da}}
    .stat-lbl{{font-size:.75rem;color:#666;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}

    /* section title */
    h2{{font-size:.9rem;color:#666;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px}}

    /* channel cards */
    .channels{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-bottom:40px}}
    .channel-card{{background:#1a1d27;border:1px solid #2a2d3a;border-radius:10px;padding:15px}}
    .channel-name{{font-weight:600;color:#fff;margin-bottom:2px}}
    .channel-meta{{font-size:.78rem;color:#5865f2;margin-bottom:10px}}
    .channel-stat{{font-size:.8rem;color:#888;margin-top:4px}}
    .last-event{{color:#aaa;margin-top:6px;font-size:.79rem}}

    /* feed */
    .feed{{background:#1a1d27;border:1px solid #2a2d3a;border-radius:12px;overflow:hidden;margin-bottom:40px}}
    .feed-row{{display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid #1f2230;flex-wrap:wrap}}
    .feed-row:last-child{{border-bottom:none}}
    .feed-badge{{font-size:.75rem;font-weight:600;padding:2px 8px;border-radius:20px;white-space:nowrap}}
    .feed-ch{{flex:1;min-width:100px;font-size:.83rem;color:#ccc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .feed-id{{font-size:.82rem;color:#7289da;white-space:nowrap}}
    .feed-time{{font-size:.75rem;color:#555;white-space:nowrap;margin-left:auto}}

    /* footer */
    .footer{{text-align:center;font-size:.75rem;color:#444}}
  </style>
</head>
<body>
<div class="container">

  <div class="header">
    <div class="dot"></div>
    <div>
      <h1>Telegram → Discord Bot</h1>
      <div class="sub">All systems operational &nbsp;·&nbsp; auto-refreshes every 30s</div>
    </div>
  </div>

  <div class="stats">
    <div class="stat"><div class="stat-val">{uptime_str}</div><div class="stat-lbl">Uptime</div></div>
    <div class="stat"><div class="stat-val">{len(targets)}</div><div class="stat-lbl">Channels Monitored</div></div>
    <div class="stat"><div class="stat-val">{total_forwarded}</div><div class="stat-lbl">Forwarded</div></div>
    <div class="stat"><div class="stat-val">{total_deleted}</div><div class="stat-lbl">Deleted</div></div>
  </div>

  <h2>Recent Forwarded Messages</h2>
  <div class="feed">
    {feed_html}
  </div>

  <h2>Monitored Channels</h2>
  <div class="channels">
    {channels_html if channels_html else '<p style="color:#555">No channels connected yet.</p>'}
  </div>

  <div class="footer">
    Last refreshed: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC
  </div>

</div>
</body>
</html>"""
    return html


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
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    time.sleep(2)

    ping_thread    = threading.Thread(target=self_ping, daemon=True)
    bot_thread     = threading.Thread(target=run_with_restart, args=("Discord Bot", "bot.py"), daemon=True)
    monitor_thread = threading.Thread(target=run_with_restart, args=("Telegram Monitor", "monitor.py"), daemon=True)

    ping_thread.start()
    bot_thread.start()
    monitor_thread.start()

    while True:
        time.sleep(60)
