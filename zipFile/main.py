import threading
import os
import subprocess
import time
from flask import Flask

# 1. إنشاء خادم وهمي (Flask Web Server) لإبقاء المشروع حياً
app = Flask('')

@app.route('/')
def home():
    return "Bot and Monitor are running 24/7!"

def run_web_server():
    # تشغيل السيرفر على البورت 8080 وهو البورت المتوقع من Replit
    app.run(host='0.0.0.0', port=8080)

# 2. دالة لتشغيل البوت
def run_bot():
    print("🤖 Starting Discord Bot...")
    subprocess.run(["python", "bot.py"])

# 3. دالة لتشغيل سكربت المراقبة
def run_monitor():
    print("🔍 Starting Telegram Monitor...")
    subprocess.run(["python", "monitor.py"])

if __name__ == "__main__":
    # تشغيل السيرفر في Thread منفصل
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    # انتظار ثوانٍ بسيطة لتأكيد إقلاع السيرفر
    time.sleep(2)
    
    # تشغيل البوت والمراقب معاً
    bot_thread = threading.Thread(target=run_bot)
    monitor_thread = threading.Thread(target=run_monitor)
    
    bot_thread.start()
    monitor_thread.start()
    
    # إبقاء الـ Main Thread حياً
    bot_thread.join()
    monitor_thread.join()