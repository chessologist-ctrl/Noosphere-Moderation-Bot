from keep_alive import keep_alive
import discord
import os
import asyncio
import json
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

PROGRESS_FILE = "perm_lock_progress.json"
PAUSE_FLAG_FILE = "pause_flag.json"

# ✅ Intents including presence, members, and message content
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Load progress file
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as f:
        progress_data = json.load(f)
else:
    progress_data = {}

# Load pause flag
if os.path.exists(PAUSE_FLAG_FILE):
    with open(PAUSE_FLAG_FILE, "r") as f:
        pause_flag = json.load(f)
else:
    pause_flag = {"paused": False}

def save_progress():
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress_data, f, indent=4)

def save_pause_flag():
    with open(PAUSE_FLAG_FILE, "w") as f:
        json.dump(pause_flag, f, indent=4)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# 🔐 Lock VC Permissions
@bot.command(name='lockvcperms')
@commands.cooldown(1, 10, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def lock_vc_permissions(ctx):
    await ctx.send("🔐 Starting permission locking process...")

    pause_flag["paused"] = False
    save_pause_flag()

    for guild in bot.guilds:
        guild_id = str(guild.id)
        if guild_id not in progress_data:
            progress_data[guild_id] = {}

        for channel in guild.channels:
            if isinstance(channel, discord.VoiceChannel):
                if pause_flag["paused"]:
                    await ctx.send("⏸️ Process paused. Use `!resume` to continue.")
                    return

                channel_id = str(channel.id)
                if channel_id not in progress_data[guild_id]:
                    progress_data[guild_id][channel_id] = {
                        "done_roles": [],
                        "total_roles_updated": 0,
                        "channel_name": channel.name
                    }

                try:
                    if "everyone" not in progress_data[guild_id][channel_id]["done_roles"]:
                        overwrite_everyone = channel.overwrites_for(guild.default_role)
                        if overwrite_everyone.send_messages is not False:
                            overwrite_everyone.send_messages = False
                            await channel.set_permissions(guild.default_role, overwrite=overwrite_everyone)
                            await asyncio.sleep(1.5)

                        progress_data[guild_id][channel_id]["done_roles"].append("everyone")
                        progress_data[guild_id][channel_id]["total_roles_updated"] += 1
                        save_progress()

                    for role in guild.roles:
                        if pause_flag["paused"]:
                            await ctx.send("⏸️ Process paused. Use `!resume` to continue.")
                            return

                        if role.is_default():
                            continue
                        if str(role.id) in progress_data[guild_id][channel_id]["done_roles"]:
                            continue

                        overwrite = channel.overwrites_for(role)
                        if overwrite.send_messages is not False:
                            overwrite.send_messages = False
                            await channel.set_permissions(role, overwrite=overwrite)
                            await asyncio.sleep(1.5)

                        progress_data[guild_id][channel_id]["done_roles"].append(str(role.id))
                        progress_data[guild_id][channel_id]["total_roles_updated"] += 1
                        save_progress()

                except Exception as e:
                    print(f"❌ Error updating {channel.name}: {e}")
                    await asyncio.sleep(3)

    await ctx.send("✅ All VC permissions locked and saved!")

# 📊 Status Command
@bot.command(name='status')
@commands.cooldown(1, 10, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def show_status(ctx):
    total_channels = 0
    total_roles_updated = 0
    report_lines = []

    for guild_id, channels in progress_data.items():
        for ch_id, ch_data in channels.items():
            ch_name = ch_data.get("channel_name", "Unknown")
            roles_done = ch_data.get("total_roles_updated", 0)
            total_channels += 1
            total_roles_updated += roles_done
            report_lines.append(f"🔹 `{ch_name}` → {roles_done} roles")

    if not report_lines:
        await ctx.send("📊 No progress yet.")
        return

    await ctx.send(f"📊 Progress Report:\nTotal Channels: **{total_channels}**\nTotal Roles Updated: **{total_roles_updated}**")
    for chunk_start in range(0, len(report_lines), 10):
        await ctx.send("\n".join(report_lines[chunk_start:chunk_start+10]))

# ♻️ Reset Progress
@bot.command(name='resetprogress')
@commands.cooldown(1, 10, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def reset_progress(ctx):
    global progress_data
    progress_data = {}
    save_progress()
    await ctx.send("♻️ Progress has been reset.")

# ⏸️ Pause Command
@bot.command(name='pause')
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def pause(ctx):
    pause_flag["paused"] = True
    save_pause_flag()
    await ctx.send("⏸️ Permission locking has been paused.")

# ▶️ Resume Command
@bot.command(name='resume')
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.has_permissions(administrator=True)
async def resume(ctx):
    pause_flag["paused"] = False
    save_pause_flag()
    await ctx.invoke(bot.get_command("lockvcperms"))

# 🧯 Cooldown and Permission Error Handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Slow down! Try again in {error.retry_after:.1f} seconds.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permissions to use this command.")
    else:
        raise error
keep_alive()
bot.run(DISCORD_TOKEN)
