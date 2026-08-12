import requests
from bs4 import BeautifulSoup
import time
import io
import json
import os
from datetime import datetime

DB_FILE = "connected_channels.json"
LAST_CHECKED_FILE = "last_checked.json"
CONFIG_FILE = "config.json"
ACTIVITY_LOG_FILE = "channel_logs.json"
MAX_ACTIVITY_ENTRIES = 100

print("Hybrid Media Monitoring & Multi-Channel Sync Online...")

sent_messages_registry = {}

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

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

def save_json(filename, data):
    path = get_path(filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ فشل حفظ {filename}: {e}")

def load_targets():
    data = load_json(DB_FILE, {})
    if data:
        print(f"📂 [قراءة ناجحة] تم تحميل {len(data)} قنوات من ملف الإعدادات.")
    else:
        print(f"⚠️ ملف الإعدادات فارغ أو غير موجود.")
    return data

def load_last_checked():
    return load_json(LAST_CHECKED_FILE, {})

def save_last_checked(data):
    save_json(LAST_CHECKED_FILE, data)

def load_config():
    return load_json(CONFIG_FILE, {})

# ─────────────────────────────────────────────
# Discord logs channel notifier
# ─────────────────────────────────────────────

DISCORD_API = "https://discord.com/api/v10"
BOT_TOKEN = ""

def post_log_message(logs_channel_id: str, embed: dict):
    if not logs_channel_id or not BOT_TOKEN:
        return
    try:
        requests.post(
            f"{DISCORD_API}/channels/{logs_channel_id}/messages",
            headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
            json={"embeds": [embed]},
            timeout=10,
        )
    except Exception as e:
        print(f"⚠️ فشل إرسال رسالة السجل: {e}")

def save_activity(entry: dict):
    logs = load_json(ACTIVITY_LOG_FILE, [])
    if not isinstance(logs, list):
        logs = []
    logs.insert(0, entry)
    logs = logs[:MAX_ACTIVITY_ENTRIES]
    save_json(ACTIVITY_LOG_FILE, logs)

def log_forwarded(channel_name: str, display_name: str, msg_id: int, tg_link: str, discord_msg_id: str, webhook_url: str):
    save_activity({
        "action": "forwarded",
        "channel": channel_name,
        "display_name": display_name,
        "msg_id": msg_id,
        "tg_link": tg_link,
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    })

    config = load_config()
    logs_channel_id = config.get("logs_channel_id")
    if not logs_channel_id:
        return

    webhook_channel_id = webhook_url.split("/")[5] if len(webhook_url.split("/")) > 5 else "?"

    embed = {
        "color": 0x2ECC71,
        "title": "🚀 تم تحويل منشور",
        "fields": [
            {"name": "📢 القناة المصدر (تليجرام)", "value": f"[{display_name}](https://t.me/{channel_name}) — `@{channel_name}`", "inline": False},
            {"name": "📌 رقم المنشور", "value": f"[#{msg_id}]({tg_link})", "inline": True},
            {"name": "📥 الوجهة (ديسكورد)", "value": f"<#{webhook_channel_id}>", "inline": True},
        ],
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "footer": {"text": "Telegram → Discord Monitor"},
    }
    post_log_message(logs_channel_id, embed)

def log_deleted(channel_name: str, display_name: str, msg_id: int):
    save_activity({
        "action": "deleted",
        "channel": channel_name,
        "display_name": display_name,
        "msg_id": msg_id,
        "tg_link": None,
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    })

    config = load_config()
    logs_channel_id = config.get("logs_channel_id")
    if not logs_channel_id:
        return

    embed = {
        "color": 0xE74C3C,
        "title": "🗑️ تم حذف منشور",
        "fields": [
            {"name": "📢 القناة (تليجرام)", "value": f"[{display_name}](https://t.me/{channel_name}) — `@{channel_name}`", "inline": False},
            {"name": "📌 رقم المنشور المحذوف", "value": f"#{msg_id}", "inline": True},
        ],
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "footer": {"text": "Telegram → Discord Monitor"},
    }
    post_log_message(logs_channel_id, embed)

# ─────────────────────────────────────────────
# Discord send with retry
# ─────────────────────────────────────────────

def send_to_discord(webhook_url, payload, files=None, retries=3):
    execute_url = f"{webhook_url}?wait=true"
    for attempt in range(1, retries + 1):
        try:
            timeout = 40 if files else 20
            if files:
                res = requests.post(execute_url, data={"payload_json": json.dumps(payload)}, files=files, timeout=timeout)
            else:
                res = requests.post(execute_url, json=payload, timeout=timeout)
            if res.status_code in [200, 201]:
                return res
            elif res.status_code == 429:
                retry_after = res.json().get("retry_after", 2)
                print(f"⏳ Rate limited — انتظار {retry_after} ثانية...")
                time.sleep(float(retry_after))
            else:
                print(f"⚠️ فشل الإرسال (محاولة {attempt}/{retries}): {res.status_code} — {res.text[:100]}")
                time.sleep(1)
        except requests.exceptions.Timeout:
            # On timeout we can't know if the message was sent — stop retrying to avoid duplicates
            print(f"⚠️ انتهى وقت الإرسال (محاولة {attempt}/{retries}) — إيقاف لتجنب التكرار")
            return None
        except Exception as e:
            print(f"⚠️ خطأ في الإرسال (محاولة {attempt}/{retries}): {e}")
            time.sleep(1)
    return None

# ─────────────────────────────────────────────
# Message payload builder
# ─────────────────────────────────────────────

def build_single_message_payload(display_name, item, channel_name, avatar_url):
    msg_id = item["id"]
    direct_post_link = f"https://t.me/{channel_name}/{msg_id}"
    target_video_source = item.get("video_url")

    embed_text = item["text"] if item["text"] else ""
    if item.get("audio_url"):
        embed_text += f"\n\n📢 **يوجد ملف صوتي مرفق بالمنشور:**\n🎵 **[استماع للملف الصوتي]({item['audio_url']})**"
    if item.get("pdf_url"):
        embed_text += f"\n\n📢 **يوجد ملف مرفق بالمنشور:**\n📁 **[تحميل واستعراض المرفق]({item['pdf_url']})**"
    embed_text += f"\n\n🔗 **[رابط المنشور]({direct_post_link})**"

    embed = {
        "color": 15844367,
        "author": {"name": display_name},
        "description": embed_text.strip() if embed_text.strip() else None,
    }
    if avatar_url:
        embed["thumbnail"] = {"url": avatar_url}

    use_attachment = item.get("use_binary_attachment", True)
    if item.get("image_url"):
        embed["image"] = {"url": "attachment://image.jpg" if use_attachment else item["image_url"]}

    payload = {}
    if target_video_source:
        payload["content"] = f"**{display_name}**"
    if embed.get("description") or embed.get("image"):
        payload["embeds"] = [embed]

    return payload, target_video_source


def send_single_item(item, display_name, channel_name, avatar_url, webhook_url):
    payload, target_video_source = build_single_message_payload(display_name, item, channel_name, avatar_url)

    files = {}
    if item.get("image_url") and item.get("use_binary_attachment", True):
        try:
            img_res = requests.get(item["image_url"], timeout=10)
            if img_res.status_code == 200:
                files["files[0]"] = ("image.jpg", io.BytesIO(img_res.content))
        except Exception:
            pass

    if target_video_source:
        try:
            vid_res = requests.get(target_video_source, timeout=15)
            if vid_res.status_code == 200:
                files["files[1]"] = ("video.mp4", io.BytesIO(vid_res.content))
        except Exception:
            pass

    return send_to_discord(webhook_url, payload, files if files else None)

# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────

last_checked_ids = load_last_checked()
print(f"📌 تم تحميل آخر مواضع مراقبة لـ {len(last_checked_ids)} قناة من الذاكرة.")

# Tracks channels that have completed their first check since startup.
# On the first check, if there are too many new messages, we skip them
# to avoid flooding Discord with old posts after a restart.
startup_checked = set()
MAX_STARTUP_CATCHUP = 3

while True:
    TARGETS = load_targets()

    if not TARGETS:
        print("No channels found in connected_channels.json. Waiting...")
        time.sleep(10)
        continue

    print(f"\n🔄 [دورة فحص جديدة] جاري فحص {len(TARGETS)} قنوات تليجرام الآن...")

    for channel_name, target_data in TARGETS.items():
        display_name = target_data["display_name"]
        webhook_url = target_data["webhook"]

        if channel_name not in last_checked_ids:
            last_checked_ids[channel_name] = None

        response = None
        for attempt in range(3):
            try:
                response = requests.get(f"https://t.me/s/{channel_name}", timeout=15)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                time.sleep(2)

        if not response or response.status_code != 200:
            print(f"❌ [{channel_name}] فشل الاتصال بصفحة التليجرام العامة.")
            continue

        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            avatar_element = soup.find('img', class_='tgme_page_photo_image')
            avatar_url = avatar_element['src'] if avatar_element and 'src' in avatar_element.attrs else None

            messages = soup.find_all('div', class_='tgme_widget_message_wrap')
            live_telegram_ids = set()

            if messages:
                first_live_id = int(messages[0].find('div', class_='tgme_widget_message')['data-post'].split('/')[-1])

                try:
                    latest_msg_id = int(messages[-1].find('div', class_='tgme_widget_message')['data-post'].split('/')[-1])
                except Exception:
                    latest_msg_id = 0

                if last_checked_ids[channel_name] is None:
                    last_checked_ids[channel_name] = latest_msg_id
                    save_last_checked(last_checked_ids)
                    print(f"📡 [{channel_name}] بدأت المراقبة بنجاح عند المنشور رقم: {latest_msg_id}")
                else:
                    print(f"🔍 [{channel_name}] يتم الفحص.. (آخر منشور مسجل: {last_checked_ids[channel_name]} | أحدث منشور حالي: {latest_msg_id})")

                new_messages = []
                seen_ids_this_cycle = set()

                for message in messages:
                    try:
                        msg_widget = message.find('div', class_='tgme_widget_message')
                        if not msg_widget or 'data-post' not in msg_widget.attrs:
                            continue

                        msg_id = int(msg_widget['data-post'].split('/')[-1])
                        live_telegram_ids.add(msg_id)

                        if msg_id in seen_ids_this_cycle:
                            continue
                        seen_ids_this_cycle.add(msg_id)

                        # Skip if already sent (guards against restart duplicates)
                        if (channel_name, msg_id) in sent_messages_registry:
                            continue

                        if msg_id > last_checked_ids[channel_name]:
                            text_element = message.find('div', class_='tgme_widget_message_text')
                            msg_text = text_element.get_text(separator="\n") if text_element else ""

                            image_element = message.find('a', class_='tgme_widget_message_photo_wrap')
                            image_url = None
                            if image_element and 'style' in image_element.attrs:
                                style = image_element['style']
                                if "background-image:url('" in style:
                                    image_url = style.split("background-image:url('")[1].split("')")[0]

                            video_element = message.find('video', class_='tgme_widget_message_video')
                            video_url = video_element['src'] if video_element and 'src' in video_element.attrs else None

                            audio_url = None
                            audio_element = message.find('audio')
                            if audio_element:
                                audio_url = audio_element.get('src') or audio_element.get('data-src')
                            if not audio_url:
                                voice_player = message.find(class_='tgme_widget_message_voice_player') or message.find(class_='tgme_widget_message_audio_player')
                                if voice_player:
                                    fallback_audio = voice_player.find('audio')
                                    if fallback_audio:
                                        audio_url = fallback_audio.get('src') or fallback_audio.get('data-src')

                            pdf_url = None
                            doc_element = message.find('a', class_='tgme_widget_message_document_wrap')
                            if doc_element and 'href' in doc_element.attrs:
                                raw_href = doc_element['href']
                                pdf_url = raw_href.replace("t.me/s/", "t.me/").replace("?single", "") if "t.me/s/" in raw_href else raw_href

                            new_messages.append({
                                "id": msg_id, "text": msg_text, "image_url": image_url,
                                "video_url": video_url, "audio_url": audio_url, "pdf_url": pdf_url
                            })
                            # Do NOT update last_checked_ids here — only after confirmed send
                    except Exception:
                        continue

                # On first startup check: if too many new messages, skip them all
                # to avoid re-flooding Discord with old posts after a restart.
                if channel_name not in startup_checked:
                    startup_checked.add(channel_name)
                    if len(new_messages) > MAX_STARTUP_CATCHUP:
                        last_checked_ids[channel_name] = latest_msg_id
                        save_last_checked(last_checked_ids)
                        print(f"⏭️ [{channel_name}] تخطي {len(new_messages)} رسالة قديمة عند بدء التشغيل — تم تحديث الموضع إلى #{latest_msg_id}")
                        new_messages = []

                for item in new_messages:
                    # Double-check: skip if already sent by a previous cycle or parallel instance
                    if (channel_name, item["id"]) in sent_messages_registry:
                        continue
                    res = send_single_item(item, display_name, channel_name, avatar_url, webhook_url)
                    if res and res.status_code in [200, 201]:
                        discord_msg_id = res.json()["id"]
                        sent_messages_registry[(channel_name, item["id"])] = {
                            "discord_msg_id": discord_msg_id,
                            "text": item["text"],
                            "image_url": item["image_url"],
                            "video_url": item["video_url"],
                            "audio_url": item["audio_url"],
                            "pdf_url": item["pdf_url"],
                        }
                        # Update and save only after confirmed successful send
                        last_checked_ids[channel_name] = item["id"]
                        save_last_checked(last_checked_ids)
                        tg_link = f"https://t.me/{channel_name}/{item['id']}"
                        log_forwarded(channel_name, display_name, item["id"], tg_link, discord_msg_id, webhook_url)
                        print(f"🚀 [{channel_name}] تم نقل المنشور رقم {item['id']} إلى ديسكورد بنجاح!")
                    else:
                        print(f"❌ [{channel_name}] فشل إرسال المنشور رقم {item['id']} بعد كل المحاولات.")

                tracked_keys = [(ch, tid) for (ch, tid) in sent_messages_registry if ch == channel_name]
                for key in tracked_keys:
                    _, tid = key
                    if tid not in live_telegram_ids and tid >= first_live_id:
                        meta = sent_messages_registry[key]
                        d_msg_id = meta["discord_msg_id"]
                        print(f"🗑️ [{channel_name}] رصد حذف منشور #{tid} — جاري الحذف من ديسكورد...")
                        try:
                            requests.delete(f"{webhook_url}/messages/{d_msg_id}", timeout=10)
                            log_deleted(channel_name, display_name, tid)
                        except Exception:
                            pass
                        del sent_messages_registry[key]

        except Exception as e:
            print(f"❌ خطأ أثناء معالجة القناة [{channel_name}]: {e}")

        time.sleep(1)

    print("💤 انتهت الدورة الحالية. جاري الانتظار لمدة 30 ثانية قبل الفحص القادم...")
    time.sleep(30)
