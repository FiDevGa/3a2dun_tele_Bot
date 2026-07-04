import discord
from discord.ext import commands
import json
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "connected_channels.json"

def load_targets():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, DB_FILE)
    
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_targets(targets):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, DB_FILE)
    
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=4)

@bot.event
async def on_ready():
    print(f"Connection Manager Bot is online as {bot.user}")

@bot.command(name="connect")
async def connect_channel(ctx, telegram_username: str, display_name: str, webhook_url: str):
    telegram_username = telegram_username.replace("https://t.me/", "").replace("@", "").strip()

    targets = load_targets()

    if telegram_username.lower() in [k.lower() for k in targets.keys()]:
        await ctx.send(f"❌ القناة `{telegram_username}` مربوطة مسبقاً بالفعل!")
        return

    targets[telegram_username] = {
        "display_name": display_name,
        "webhook": webhook_url
    }

    save_targets(targets)
    await ctx.send(f"✅ تم بنجاح ربط القناة وحفظها بملف الإعدادات!\n• معرف التليجرام: `{telegram_username}`\n• اسم العرض: **{display_name}**")

@connect_channel.error
async def connect_channel_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ الاستخدام الصحيح: `!connect telegram_channel_id display_name webhook_url`")

# جلب التوكن بأمان من Replit Secrets
TOKEN = os.environ.get('DISCORD_TOKEN')

if not TOKEN:
    print("❌ خطأ: لم يتم العثور على المفتاح 'DISCORD_TOKEN' في أداة Secrets الخاصة بـ Replit!")
else:
    bot.run(TOKEN)
