import requests
from bs4 import BeautifulSoup
import time
import io
import json
import os

DB_FILE = "connected_channels.json"
print("Hybrid Media Monitoring & Multi-Channel Sync Online...")

last_checked_ids = {}
sent_messages_registry = {}

def load_targets():
    # استخدام المسار المطلق لضمان العثور على الملف أينما تم تشغيل السكربت
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, DB_FILE)
    
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    print(f"📂 [قراءة ناجحة] تم تحميل {len(data)} قنوات من ملف الإعدادات.")
                return data
        except Exception as e:
            print(f"❌ خطأ أثناء قراءة ملف الـ JSON: {e}")
            return {}
    else:
        print(f"⚠️ ملف الإعدادات غير موجود في المسار المتوقع: {full_path}")
    return {}

def build_split_media_payload(display_name, items_list, channel_name, avatar_url):
    embeds = []
    total_items = len(items_list)
    main_content_text = ""
    target_video_source = None
    last_post_id = items_list[-1]["id"] if total_items > 0 else 0
    direct_post_link = f"https://t.me/{channel_name}/{last_post_id}"
    
    if total_items > 0 and items_list[0]["video_url"]:
        msg1_text = items_list[0]["text"]
        target_video_source = items_list[0]["video_url"]
        
        main_content_text = f"**{display_name}**"
        first_embed_text = msg1_text if msg1_text else ""
        
        if items_list[0]["audio_url"]:
            first_embed_text += f"\n\n📢 **يوجد ملف صوتي مرفق بالمنشور:**\n🎵 **[استماع للملف الصوتي]({items_list[0]['audio_url']})**"
        if items_list[0]["pdf_url"]:
            first_embed_text += f"\n\n📢 **يوجد ملف مرفق بالمنشور:**\n📁 **[تحميل واستعراض المرفق]({items_list[0]['pdf_url']})**"
        if total_items == 1:
            first_embed_text += f"\n\n🔗 **[رابط المنشور]({direct_post_link})**"
            
        main_embed = {"description": first_embed_text if first_embed_text else None, "color": 15844367}
        if avatar_url:
            main_embed["thumbnail"] = {"url": avatar_url}
        if items_list[0]["image_url"]:
            main_embed["image"] = {"url": "attachment://image.jpg" if items_list[0].get("use_binary_attachment", True) else items_list[0]["image_url"]}
            
        embeds.append(main_embed)
        
        for i in range(1, total_items):
            item = items_list[i]
            current_text = item["text"]
            if item["audio_url"]:
                current_text += f"\n\n📢 **يوجد ملف صوتي مرفق:**\n🎵 **[استماع]({item['audio_url']})**"
            if item["pdf_url"]:
                current_text += f"\n\n📢 **يوجد ملف مرفق:**\n📁 **[تحميل]({item['pdf_url']})**"
            if i == total_items - 1:
                current_text += f"\n\n🔗 **[رابط المنشور]({direct_post_link})**"
            current_text = "───────────────────\n\n" + current_text
            embed = {"description": current_text, "color": 15844367}
            if item["image_url"]:
                embed["image"] = {"url": "attachment://image.jpg" if item.get("use_binary_attachment", True) else item["image_url"]}
            embeds.append(embed)
    else:
        for i, item in enumerate(items_list):
            current_text = item["text"]
            if item["audio_url"]:
                current_text += f"\n\n📢 **يوجد ملف صوتي مرفق:**\n🎵 **[استماع]({item['audio_url']})**"
            if item["pdf_url"]:
                current_text += f"\n\n📢 **يوجد ملف مرفق:**\n📁 **[تحميل]({item['pdf_url']})**"
            if i == total_items - 1:
                current_text += f"\n\n🔗 **[رابط المنشور]({direct_post_link})**"
            if i > 0 and current_text:
                current_text = "───────────────────\n\n" + current_text
            embed = {"description": current_text if current_text else None, "color": 15844367}
            if i == 0:
                embed["author"] = {"name": display_name}
                if avatar_url:
                    embed["thumbnail"] = {"url": avatar_url}
            if item["image_url"]:
                embed["image"] = {"url": "attachment://image.jpg" if item.get("use_binary_attachment", True) else item["image_url"]}
            embeds.append(embed)

    payload = {}
    if main_content_text:
        payload["content"] = main_content_text
    if embeds:
        payload["embeds"] = embeds
    return payload, target_video_source

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
                    print(f"📡 [{channel_name}] بدأت المراقبة بنجاح عند المنشور رقم: {latest_msg_id}")
                else:
                    print(f"🔍 [{channel_name}] يتم الفحص.. (آخر منشور مسجل: {last_checked_ids[channel_name]} | أحدث منشور حالي: {latest_msg_id})")

                new_messages_batch = []

                for message in messages:
                    try:
                        msg_widget = message.find('div', class_='tgme_widget_message')
                        if not msg_widget or 'data-post' not in msg_widget.attrs:
                            continue
                            
                        msg_id = int(msg_widget['data-post'].split('/')[-1])
                        live_telegram_ids.add(msg_id)
                        
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
                                    
                            new_messages_batch.append({
                                "id": msg_id, "text": msg_text, "image_url": image_url, 
                                "video_url": video_url, "audio_url": audio_url, "pdf_url": pdf_url
                            })
                            last_checked_ids[channel_name] = msg_id
                    except Exception:
                        continue

                if new_messages_batch:
                    all_ids_in_this_stack = [m["id"] for m in new_messages_batch]
                    target_image_url = next((m["image_url"] for m in new_messages_batch if m["image_url"]), None)
                    
                    payload, target_video_source = build_split_media_payload(display_name, new_messages_batch, channel_name, avatar_url)
                    
                    files = {}
                    if target_image_url:
                        try:
                            img_res = requests.get(target_image_url, timeout=10)
                            if img_res.status_code == 200:
                                files["files[0]"] = ("image.jpg", io.BytesIO(img_res.content))
                        except Exception: pass
                            
                    if target_video_source:
                        try:
                            vid_res = requests.get(target_video_source, timeout=15)
                            if vid_res.status_code == 200:
                                files["files[1]"] = ("video.mp4", io.BytesIO(vid_res.content))
                        except Exception: pass

                    execute_url = f"{webhook_url}?wait=true"
                    res = requests.post(execute_url, data={"payload_json": json.dumps(payload)}, files=files) if files else requests.post(execute_url, json=payload)
                    
                    if res.status_code in [200, 201]:
                        discord_msg_id = res.json()["id"]
                        for m in new_messages_batch:
                            sent_messages_registry[m["id"]] = {
                                "discord_msg_id": discord_msg_id, "text": m["text"], "image_url": m["image_url"],
                                "video_url": m["video_url"], "audio_url": m["audio_url"], "pdf_url": m["pdf_url"], 
                                "tg_channel": channel_name, "all_ids_in_stack": all_ids_in_this_stack
                            }
                        print(f"🚀 [{channel_name}] تم نقل منشورات جديدة إلى ديسكورد بنجاح!")

            tracked_ids_for_this_channel = [tid for tid, data in sent_messages_registry.items() if data["tg_channel"] == channel_name]
            
            for tid in tracked_ids_for_this_channel:
                if tid not in live_telegram_ids and tid >= first_live_id:
                    meta = sent_messages_registry[tid]
                    d_msg_id = meta["discord_msg_id"]
                    stack_list = meta["all_ids_in_stack"]
                    
                    print(f"🗑️ [{channel_name}] تم رصد حذف منشور على تليجرام، جاري الحذف من ديسكورد للرقم: {tid}")
                    remaining_ids_in_stack = [sid for sid in stack_list if sid != tid and sid in sent_messages_registry]
                    
                    if not remaining_ids_in_stack:
                        try:
                            requests.delete(f"{webhook_url}/messages/{d_msg_id}")
                        except Exception: pass
                    else:
                        surviving_items = []
                        for sid in remaining_ids_in_stack:
                            surviving_items.append({
                                "id": sid, "text": sent_messages_registry[sid]["text"], "image_url": sent_messages_registry[sid]["image_url"],
                                "video_url": sent_messages_registry[sid]["video_url"], "audio_url": sent_messages_registry[sid]["audio_url"],
                                "pdf_url": sent_messages_registry[sid]["pdf_url"], "use_binary_attachment": False
                            })
                        
                        edit_payload, _ = build_split_media_payload(display_name, surviving_items, channel_name, avatar_url)
                        for sid in remaining_ids_in_stack:
                            sent_messages_registry[sid]["all_ids_in_stack"] = remaining_ids_in_stack
                            
                        try:
                            requests.patch(f"{webhook_url}/messages/{d_msg_id}", json=edit_payload)
                        except Exception: pass
                        
                    del sent_messages_registry[tid]
                    
        except Exception as e:
            print(f"❌ خطأ أثناء معالجة القناة [{channel_name}]: {e}")
            
        time.sleep(1)
        
    print("💤 انتهت الدورة الحالية. جاري الانتظار لمدة 30 ثانية قبل الفحص القادم...")
    time.sleep(30)