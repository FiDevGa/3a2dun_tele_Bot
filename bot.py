import discord
from discord.ext import commands
import discord.app_commands
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

BOT_START_TIME = time.time()
DB_FILE = "connected_channels.json"
CONFIG_FILE = "config.json"

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

def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, CONFIG_FILE)
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, CONFIG_FILE)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


# ─────────────────────────────────────────────
# Permission helpers
# ─────────────────────────────────────────────

def has_staff_permission(ctx) -> bool:
    """Returns True if the user is a server admin or has a configured staff role."""
    # Handle both discord.Interaction and commands.Context
    if hasattr(ctx, 'user'):
        # This is an Interaction
        user = ctx.user
        guild = ctx.guild
    else:
        # This is a Context
        user = ctx.author
        guild = ctx.guild
    
    if guild is None:
        return False
    if user.guild_permissions.administrator:
        return True
    config = load_config()
    staff_roles = config.get("staff_role_ids", [])
    user_role_ids = [str(r.id) for r in user.roles]
    return any(rid in user_role_ids for rid in staff_roles)

def staff_check():
    async def predicate(ctx):
        if not has_staff_permission(ctx):
            embed = discord.Embed(
                title="🚫 ليس لديك صلاحية",
                description="هذا الأمر مخصص للمشرفين فقط. اطلب من مدير السيرفر إضافة رتبتك بـ `/staff add @الرتبة`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return False
        return True
    return commands.check(predicate)


# ─────────────────────────────────────────────
# Block DMs
# ─────────────────────────────────────────────

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.guild is None:
        return
    await bot.process_commands(message)


# ─────────────────────────────────────────────
# Edit feature
# ─────────────────────────────────────────────

class EditModal(discord.ui.Modal):
    def __init__(self, channel_key: str, current_data: dict):
        super().__init__(title=f"تعديل: {current_data['display_name'][:40]}")
        self.channel_key = channel_key

        self.new_id = discord.ui.TextInput(label="معرف قناة تليجرام", default=channel_key, required=True, max_length=100)
        self.new_name = discord.ui.TextInput(label="اسم العرض", default=current_data["display_name"], required=True, max_length=100)
        self.new_webhook = discord.ui.TextInput(label="رابط Webhook", default=current_data["webhook"], required=True, max_length=500, style=discord.TextStyle.paragraph)
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
        targets[new_key] = {"display_name": new_name, "webhook": new_webhook}
        save_targets(targets)
        embed = discord.Embed(title="✅ تم الحفظ بنجاح", color=discord.Color.green())
        embed.add_field(name="معرف التليجرام", value=f"`{new_key}`", inline=False)
        embed.add_field(name="اسم العرض", value=new_name, inline=False)
        wh = new_webhook
        embed.add_field(name="Webhook", value=f"`{wh[:60]}...`" if len(wh) > 60 else f"`{wh}`", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)


class EditPanelView(discord.ui.View):
    def __init__(self, channel_key: str, channel_data: dict):
        super().__init__(timeout=120)
        self.channel_key = channel_key
        self.channel_data = channel_data

    @discord.ui.button(label="✏️ تعديل", style=discord.ButtonStyle.primary)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditModal(self.channel_key, self.channel_data))

    @discord.ui.button(label="❌ إغلاق", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="🔒 تم إغلاق لوحة التعديل", color=discord.Color.greyple()), view=None)


class DeleteConfirmView(discord.ui.View):
    def __init__(self, channel_key: str):
        super().__init__(timeout=60)
        self.channel_key = channel_key

    @discord.ui.button(label="✅ تأكيد الحذف", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        targets = load_targets()
        display = targets.get(self.channel_key, {}).get("display_name", self.channel_key)
        if self.channel_key in targets:
            del targets[self.channel_key]
            save_targets(targets)
            embed = discord.Embed(title="✅ تم الحذف", description=f"تم حذف القناة **{display}** من قائمة المراقبة.", color=discord.Color.green())
        else:
            embed = discord.Embed(title="❌ القناة غير موجودة", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ إلغاء", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="↩️ تم الإلغاء", color=discord.Color.greyple()), view=None)


class ChannelSelectView(discord.ui.View):
    def __init__(self, targets: dict, mode: str):
        super().__init__(timeout=60)
        self.targets = targets
        self.mode = mode

        options = [
            discord.SelectOption(label=data["display_name"][:100], value=key, description=f"@{key}"[:100])
            for key, data in list(targets.items())[:25]
        ]

        placeholder_map = {
            "edit": "اختر القناة التي تريد تعديلها...",
            "delete": "اختر القناة التي تريد حذفها...",
        }

        select = discord.ui.Select(placeholder=placeholder_map.get(mode, "اختر قناة..."), options=options)
        select.callback = self.select_callback
        self.add_item(select)

    @discord.ui.button(label="🔒 إغلاق", style=discord.ButtonStyle.secondary, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="🔒 تم الإغلاق", color=discord.Color.greyple()), view=None)

    async def select_callback(self, interaction: discord.Interaction):
        selected_key = interaction.data["values"][0]
        data = self.targets.get(selected_key)
        if not data:
            await interaction.response.edit_message(content="❌ لم يتم العثور على هذه القناة.", view=None)
            return

        if self.mode == "edit":
            embed = discord.Embed(title=f"📋 تعديل: {data['display_name']}", color=discord.Color.blurple())
            embed.add_field(name="معرف التليجرام", value=f"`{selected_key}`", inline=False)
            embed.add_field(name="اسم العرض", value=data["display_name"], inline=False)
            wh = data["webhook"]
            embed.add_field(name="Webhook", value=f"`{wh[:60]}...`" if len(wh) > 60 else f"`{wh}`", inline=False)
            await interaction.response.edit_message(embed=embed, view=EditPanelView(selected_key, data))

        elif self.mode == "delete":
            embed = discord.Embed(
                title=f"🗑️ حذف القناة: {data['display_name']}",
                description="هل أنت متأكد أنك تريد حذف هذه القناة من قائمة المراقبة؟",
                color=discord.Color.red(),
            )
            embed.add_field(name="معرف التليجرام", value=f"`{selected_key}`", inline=False)
            await interaction.response.edit_message(embed=embed, view=DeleteConfirmView(selected_key))


# ─────────────────────────────────────────────
# Bot events & commands
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"Connection Manager Bot is online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.command(name="staff")
async def staff_cmd(ctx, action: str = None, role: discord.Role = None):
    if ctx.guild is None:
        return
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="🚫 للمديرين فقط",
            description="أمر `/staff` مخصص لمديري السيرفر فقط.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    config = load_config()
    staff_roles = config.get("staff_role_ids", [])

    if action is None or action.lower() == "list":
        if not staff_roles:
            desc = "لا توجد رتب staff مضافة حالياً.\nاستخدم `/staff add @الرتبة` لإضافة رتبة."
        else:
            role_mentions = []
            for rid in staff_roles:
                r = ctx.guild.get_role(int(rid))
                role_mentions.append(r.mention if r else f"(رتبة محذوفة: {rid})")
            desc = "\n".join(role_mentions)
        embed = discord.Embed(title="👥 رتب Staff المصرح لها", description=desc, color=discord.Color.blurple())
        embed.set_footer(text="/staff add @رتبة — /staff remove @رتبة")
        await ctx.send(embed=embed)

    elif action.lower() == "add":
        if role is None:
            await ctx.send("❌ حدد الرتبة: `/staff add @الرتبة`")
            return
        role_id = str(role.id)
        if role_id in staff_roles:
            await ctx.send(f"⚠️ الرتبة {role.mention} مضافة مسبقاً.")
            return
        staff_roles.append(role_id)
        config["staff_role_ids"] = staff_roles
        save_config(config)
        embed = discord.Embed(
            title="✅ تمت الإضافة",
            description=f"أصبح لأعضاء {role.mention} صلاحية استخدام أوامر البوت.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    elif action.lower() == "remove":
        if role is None:
            await ctx.send("❌ حدد الرتبة: `/staff remove @الرتبة`")
            return
        role_id = str(role.id)
        if role_id not in staff_roles:
            await ctx.send(f"⚠️ الرتبة {role.mention} غير موجودة في القائمة.")
            return
        staff_roles.remove(role_id)
        config["staff_role_ids"] = staff_roles
        save_config(config)
        embed = discord.Embed(
            title="✅ تمت الإزالة",
            description=f"تم سحب صلاحية البوت من أعضاء {role.mention}.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    else:
        await ctx.send("❌ استخدام غير صحيح.\n`/staff list` — `/staff add @رتبة` — `/staff remove @رتبة`")

@staff_cmd.error
async def staff_error(ctx, error):
    if isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ لم يتم العثور على الرتبة. استخدم @mention أو اسم الرتبة.")


@bot.command(name="connect")
@staff_check()
async def connect_channel(ctx, telegram_username: str, display_name: str, webhook_url: str):
    telegram_username = telegram_username.replace("https://t.me/", "").replace("@", "").strip()
    targets = load_targets()
    if telegram_username.lower() in [k.lower() for k in targets.keys()]:
        await ctx.send(f"❌ القناة `{telegram_username}` مربوطة مسبقاً بالفعل!")
        return
    targets[telegram_username] = {"display_name": display_name, "webhook": webhook_url}
    save_targets(targets)
    await ctx.send(f"✅ تم ربط القناة وحفظها!\n• معرف التليجرام: `{telegram_username}`\n• اسم العرض: **{display_name}**")

@connect_channel.error
async def connect_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ الاستخدام الصحيح: `/connect telegram_channel_id display_name webhook_url`")
    elif isinstance(error, commands.CheckFailure):
        pass


@bot.command(name="edit")
@staff_check()
async def edit_channel(ctx):
    targets = load_targets()
    if not targets:
        await ctx.send("❌ لا توجد قنوات مربوطة حالياً.")
        return
    embed = discord.Embed(title="✏️ تعديل القنوات المربوطة", description="اختر القناة التي تريد تعديلها:", color=discord.Color.blurple())
    await ctx.send(embed=embed, view=ChannelSelectView(targets, mode="edit"))

@edit_channel.error
async def edit_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass


@bot.command(name="delete")
@staff_check()
async def delete_channel(ctx):
    targets = load_targets()
    if not targets:
        await ctx.send("❌ لا توجد قنوات مربوطة حالياً.")
        return
    embed = discord.Embed(title="🗑️ حذف قناة مربوطة", description="اختر القناة التي تريد حذفها:", color=discord.Color.red())
    await ctx.send(embed=embed, view=ChannelSelectView(targets, mode="delete"))

@delete_channel.error
async def delete_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass


@bot.command(name="list")
@staff_check()
async def list_channels(ctx):
    targets = load_targets()
    if not targets:
        await ctx.send("❌ لا توجد قنوات مربوطة حالياً.")
        return
    embed = discord.Embed(title=f"📡 القنوات المربوطة ({len(targets)})", color=discord.Color.blurple())
    for key, data in targets.items():
        embed.add_field(name=data["display_name"], value=f"🔗 `@{key}`", inline=False)
    await ctx.send(embed=embed)

@list_channels.error
async def list_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass


@bot.command(name="status")
@staff_check()
async def bot_status(ctx):
    targets = load_targets()
    uptime_seconds = int(time.time() - BOT_START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}س {minutes}د {seconds}ث"
    config = load_config()
    logs_channel_id = config.get("logs_channel_id")
    logs_channel_str = f"<#{logs_channel_id}>" if logs_channel_id else "غير محدد"
    embed = discord.Embed(title="📊 حالة البوت", color=discord.Color.green())
    embed.add_field(name="🤖 البوت", value=str(bot.user), inline=False)
    embed.add_field(name="⏱️ وقت التشغيل", value=uptime_str, inline=True)
    embed.add_field(name="📡 القنوات المراقبة", value=str(len(targets)), inline=True)
    embed.add_field(name="📋 قناة السجلات", value=logs_channel_str, inline=False)
    await ctx.send(embed=embed)

@bot_status.error
async def status_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass


@bot.command(name="setlogs")
@staff_check()
async def set_logs_channel(ctx, channel: discord.TextChannel = None):
    if channel is None:
        channel = ctx.channel

    config = load_config()
    config["logs_channel_id"] = str(channel.id)
    save_config(config)

    embed = discord.Embed(
        title="✅ تم تعيين قناة السجلات",
        description=f"سيتم إرسال سجل أحداث المراقبة إلى {channel.mention}",
        color=discord.Color.green(),
    )
    embed.add_field(name="ما الذي سيُسجَّل؟", value="🚀 كل رسالة يتم تحويلها من تليجرام إلى ديسكورد\n🗑️ كل رسالة يتم حذفها من ديسكورد", inline=False)
    await ctx.send(embed=embed)

@set_logs_channel.error
async def setlogs_error(ctx, error):
    if isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ لم يتم العثور على القناة. استخدم `/setlogs #اسم-القناة` أو اكتب الأمر في القناة المطلوبة.")
    elif isinstance(error, commands.CheckFailure):
        pass


# ─────────────────────────────────────────────
# Slash Commands
# ─────────────────────────────────────────────

@bot.tree.command(name="staff", description="إدارة رتب الموظفين الذين يمكنهم استخدام الأوامر")
async def slash_staff(interaction: discord.Interaction, action: str = None, role: discord.Role = None):
    """إدارة رتب الموظفين"""
    if interaction.guild is None:
        return
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="🚫 للمديرين فقط",
            description="أمر `/staff` مخصص لمديري السيرفر فقط.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    config = load_config()
    staff_roles = config.get("staff_role_ids", [])

    if action is None or action.lower() == "list":
        if not staff_roles:
            desc = "لا توجد رتب staff مضافة حالياً.\nاستخدم `/staff add @الرتبة` لإضافة رتبة."
        else:
            role_mentions = []
            for rid in staff_roles:
                r = interaction.guild.get_role(int(rid))
                role_mentions.append(r.mention if r else f"(رتبة محذوفة: {rid})")
            desc = "\n".join(role_mentions)
        embed = discord.Embed(title="👥 رتب Staff المصرح لها", description=desc, color=discord.Color.blurple())
        embed.set_footer(text="/staff add @رتبة — /staff remove @رتبة")
        await interaction.response.send_message(embed=embed)

    elif action.lower() == "add":
        if role is None:
            await interaction.response.send_message("❌ حدد الرتبة: `/staff add @الرتبة`")
            return
        role_id = str(role.id)
        if role_id in staff_roles:
            await interaction.response.send_message(f"⚠️ الرتبة {role.mention} مضافة مسبقاً.")
            return
        staff_roles.append(role_id)
        config["staff_role_ids"] = staff_roles
        save_config(config)
        embed = discord.Embed(
            title="✅ تمت الإضافة",
            description=f"أصبح لأعضاء {role.mention} صلاحية استخدام أوامر البوت.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    elif action.lower() == "remove":
        if role is None:
            await interaction.response.send_message("❌ حدد الرتبة: `/staff remove @الرتبة`")
            return
        role_id = str(role.id)
        if role_id not in staff_roles:
            await interaction.response.send_message(f"⚠️ الرتبة {role.mention} غير موجودة في القائمة.")
            return
        staff_roles.remove(role_id)
        config["staff_role_ids"] = staff_roles
        save_config(config)
        embed = discord.Embed(
            title="✅ تمت الإزالة",
            description=f"تم سحب صلاحية البوت من أعضاء {role.mention}.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    else:
        await interaction.response.send_message("❌ استخدام غير صحيح.\n`/staff list` — `/staff add @رتبة` — `/staff remove @رتبة`")


@bot.tree.command(name="list", description="عرض قائمة القنوات المربوطة")
async def slash_list(interaction: discord.Interaction):
    """عرض القنوات المربوطة"""
    if not has_staff_permission(interaction):
        embed = discord.Embed(
            title="🚫 ليس لديك صلاحية",
            description="هذا الأمر مخصص للمشرفين فقط.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    targets = load_targets()
    if not targets:
        await interaction.response.send_message("❌ لا توجد قنوات مربوطة حالياً.")
        return
    embed = discord.Embed(title=f"📡 القنوات المربوطة ({len(targets)})", color=discord.Color.blurple())
    for key, data in targets.items():
        embed.add_field(name=data["display_name"], value=f"🔗 `@{key}`", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="status", description="عرض حالة البوت الحالية")
async def slash_status(interaction: discord.Interaction):
    """عرض حالة البوت"""
    if not has_staff_permission(interaction):
        embed = discord.Embed(
            title="🚫 ليس لديك صلاحية",
            description="هذا الأمر مخصص للمشرفين فقط.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    targets = load_targets()
    uptime_seconds = int(time.time() - BOT_START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}س {minutes}د {seconds}ث"
    config = load_config()
    logs_channel_id = config.get("logs_channel_id")
    logs_channel_str = f"<#{logs_channel_id}>" if logs_channel_id else "غير محدد"
    embed = discord.Embed(title="📊 حالة البوت", color=discord.Color.green())
    embed.add_field(name="🤖 البوت", value=str(bot.user), inline=False)
    embed.add_field(name="⏱️ وقت التشغيل", value=uptime_str, inline=True)
    embed.add_field(name="📡 القنوات المراقبة", value=str(len(targets)), inline=True)
    embed.add_field(name="📋 قناة السجلات", value=logs_channel_str, inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="setlogs", description="تعيين قناة السجلات")
async def slash_setlogs(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """تعيين قناة السجلات"""
    if not has_staff_permission(interaction):
        embed = discord.Embed(
            title="🚫 ليس لديك صلاحية",
            description="هذا الأمر مخصص للمشرفين فقط.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    if channel is None:
        channel = interaction.channel

    config = load_config()
    config["logs_channel_id"] = str(channel.id)
    save_config(config)

    embed = discord.Embed(
        title="✅ تم تعيين قناة السجلات",
        description=f"سيتم إرسال سجل أحداث المراقبة إلى {channel.mention}",
        color=discord.Color.green(),
    )
    embed.add_field(name="ما الذي سيُسجَّل؟", value="🚀 كل رسالة يتم تحويلها من تليجرام إلى ديسكورد\n🗑️ كل رسالة يتم حذفها من ديسكورد", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="connect", description="ربط قناة تليجرام بالديسكورد")
async def slash_connect(interaction: discord.Interaction, telegram_username: str, display_name: str, webhook_url: str):
    """ربط قناة تليجرام"""
    if not has_staff_permission(interaction):
        embed = discord.Embed(
            title="🚫 ليس لديك صلاحية",
            description="هذا الأمر مخصص للمشرفين فقط.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    telegram_username = telegram_username.replace("https://t.me/", "").replace("@", "").strip()
    targets = load_targets()
    if telegram_username.lower() in [k.lower() for k in targets.keys()]:
        await interaction.response.send_message(f"❌ القناة `{telegram_username}` مربوطة مسبقاً بالفعل!")
        return
    targets[telegram_username] = {"display_name": display_name, "webhook": webhook_url}
    save_targets(targets)
    await interaction.response.send_message(f"✅ تم ربط القناة وحفظها!\n• معرف التليجرام: `{telegram_username}`\n• اسم العرض: **{display_name}**")


@bot.tree.command(name="edit", description="تعديل قناة مربوطة")
async def slash_edit(interaction: discord.Interaction):
    """تعديل القنوات"""
    if not has_staff_permission(interaction):
        embed = discord.Embed(
            title="🚫 ليس لديك صلاحية",
            description="هذا الأمر مخصص للمشرفين فقط.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    targets = load_targets()
    if not targets:
        await interaction.response.send_message("❌ لا توجد قنوات مربوطة حالياً.")
        return
    embed = discord.Embed(title="✏️ تعديل القنوات المربوطة", description="اختر القناة التي تريد تعديلها:", color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, view=ChannelSelectView(targets, mode="edit"))


@bot.tree.command(name="delete", description="حذف قناة مربوطة")
async def slash_delete(interaction: discord.Interaction):
    """حذف القنوات"""
    if not has_staff_permission(interaction):
        embed = discord.Embed(
            title="🚫 ليس لديك صلاحية",
            description="هذا الأمر مخصص للمشرفين فقط.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    targets = load_targets()
    if not targets:
        await interaction.response.send_message("❌ لا توجد قنوات مربوطة حالياً.")
        return
    embed = discord.Embed(title="🗑️ حذف قناة مربوطة", description="اختر القناة التي تريد حذفها:", color=discord.Color.red())
    await interaction.response.send_message(embed=embed, view=ChannelSelectView(targets, mode="delete"))


TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ خطأ: لم يتم العثور على المفتاح 'TOKEN' في ملف .env!")
else:
    bot.run(TOKEN)
