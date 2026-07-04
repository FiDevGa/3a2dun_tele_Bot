import discord
from discord.ext import commands
from discord import app_commands
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


class EditModal(discord.ui.Modal):
    def __init__(self, channel_key: str, current_data: dict):
        super().__init__(title=f"تعديل: {current_data['display_name']}")
        self.channel_key = channel_key

        self.new_id = discord.ui.TextInput(
            label="معرف قناة تليجرام",
            default=channel_key,
            required=True,
            max_length=100,
        )
        self.new_name = discord.ui.TextInput(
            label="اسم العرض",
            default=current_data["display_name"],
            required=True,
            max_length=100,
        )
        self.new_webhook = discord.ui.TextInput(
            label="رابط Webhook",
            default=current_data["webhook"],
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.new_id)
        self.add_item(self.new_name)
        self.add_item(self.new_webhook)

    async def on_submit(self, interaction: discord.Interaction):
        targets = load_targets()

        old_key = self.channel_key
        new_key = self.new_id.value.strip().replace("https://t.me/", "").replace("@", "")
        new_name = self.new_name.value.strip()
        new_webhook = self.new_webhook.value.strip()

        if old_key in targets:
            del targets[old_key]

        targets[new_key] = {
            "display_name": new_name,
            "webhook": new_webhook,
        }
        save_targets(targets)

        embed = discord.Embed(
            title="✅ تم الحفظ بنجاح",
            color=discord.Color.green(),
        )
        embed.add_field(name="معرف التليجرام", value=f"`{new_key}`", inline=False)
        embed.add_field(name="اسم العرض", value=new_name, inline=False)
        embed.add_field(name="Webhook", value=f"`{new_webhook[:60]}...`" if len(new_webhook) > 60 else f"`{new_webhook}`", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)


class EditPanelView(discord.ui.View):
    def __init__(self, channel_key: str, channel_data: dict):
        super().__init__(timeout=120)
        self.channel_key = channel_key
        self.channel_data = channel_data

    @discord.ui.button(label="✏️ تعديل", style=discord.ButtonStyle.primary)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditModal(self.channel_key, self.channel_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ إغلاق", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="🔒 تم إغلاق لوحة التعديل", color=discord.Color.greyple()),
            view=None,
        )

    async def on_timeout(self):
        pass


class ConnectionSelectView(discord.ui.View):
    def __init__(self, targets: dict):
        super().__init__(timeout=60)
        self.targets = targets

        options = [
            discord.SelectOption(
                label=data["display_name"][:100],
                value=key,
                description=f"@{key}"[:100],
            )
            for key, data in list(targets.items())[:25]
        ]

        select = discord.ui.Select(
            placeholder="اختر القناة التي تريد تعديلها...",
            options=options,
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_key = interaction.data["values"][0]
        data = self.targets.get(selected_key)

        if not data:
            await interaction.response.edit_message(
                content="❌ لم يتم العثور على هذه القناة.",
                view=None,
            )
            return

        embed = discord.Embed(
            title=f"📋 تعديل القناة: {data['display_name']}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="معرف التليجرام", value=f"`{selected_key}`", inline=False)
        embed.add_field(name="اسم العرض", value=data["display_name"], inline=False)
        embed.add_field(
            name="Webhook",
            value=f"`{data['webhook'][:60]}...`" if len(data["webhook"]) > 60 else f"`{data['webhook']}`",
            inline=False,
        )

        panel_view = EditPanelView(selected_key, data)
        await interaction.response.edit_message(embed=embed, view=panel_view)


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
        "webhook": webhook_url,
    }
    save_targets(targets)
    await ctx.send(
        f"✅ تم بنجاح ربط القناة وحفظها بملف الإعدادات!\n"
        f"• معرف التليجرام: `{telegram_username}`\n"
        f"• اسم العرض: **{display_name}**"
    )


@connect_channel.error
async def connect_channel_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ الاستخدام الصحيح: `!connect telegram_channel_id display_name webhook_url`")


@bot.command(name="edit")
async def edit_channel(ctx):
    targets = load_targets()
    if not targets:
        await ctx.send("❌ لا توجد قنوات مربوطة حالياً.")
        return

    embed = discord.Embed(
        title="✏️ تعديل القنوات المربوطة",
        description="اختر القناة التي تريد تعديلها من القائمة أدناه:",
        color=discord.Color.blurple(),
    )
    view = ConnectionSelectView(targets)
    await ctx.send(embed=embed, view=view)


TOKEN = os.environ.get('DISCORD_TOKEN')

if not TOKEN:
    print("❌ خطأ: لم يتم العثور على المفتاح 'DISCORD_TOKEN' في أداة Secrets الخاصة بـ Replit!")
else:
    bot.run(TOKEN)
