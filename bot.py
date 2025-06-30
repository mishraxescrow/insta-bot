import asyncio
import random
import string
import json
import os
from datetime import datetime, timedelta

from telegram import Update, Bot, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

BOT_TOKEN = "8010738634:AAFoGbZW9Heaz-mtQk8qyHTc1N8m3eUkzuM"
LOG_BOT_TOKEN = "7404756763:AAE5VxoUOsO_59Tgtvvnyg6n-S8Wknc1MTs"
ADMIN_ID = 6684244590
DATA_FILE = "data.json"

user_keys = {}
shared_keys = {}
monitoring_sessions = {}

log_bot = Bot(LOG_BOT_TOKEN)

def load_data():
    global user_keys, shared_keys
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            user_keys.update({
                int(k): {
                    "name": v["name"],
                    "key": v["key"],
                    "expires": datetime.fromisoformat(v["expires"])
                } for k, v in data.get("user_keys", {}).items()
            })
            shared_keys.update({
                k: {
                    "name": v["name"],
                    "expires": datetime.fromisoformat(v["expires"])
                } for k, v in data.get("shared_keys", {}).items()
            })

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "user_keys": {
                str(k): {
                    "name": v["name"],
                    "key": v["key"],
                    "expires": v["expires"].isoformat()
                } for k, v in user_keys.items()
            },
            "shared_keys": {
                k: {
                    "name": v["name"],
                    "expires": v["expires"].isoformat()
                } for k, v in shared_keys.items()
            }
        }, f, indent=2)

def format_duration(td: timedelta):
    total_seconds = int(td.total_seconds())
    minutes = total_seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours} hr {minutes} mins" if hours else f"{minutes} mins"

def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def validate_key(user_id):
    data = user_keys.get(user_id)
    if not data:
        return False, "❌ No active key. Use /usekey <key> to activate one."
    if data["expires"] < datetime.now():
        return False, "❌ Your key has expired."
    return True, data

async def check_status(username: str) -> bool:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context()).new_page()
            await page.goto(f"https://www.instagram.com/{username}/", timeout=10000)
            html = await page.content()
            await browser.close()
            return "Sorry, this page isn't available." not in html
    except:
        return False

async def monitor_task(user_id: int, username: str, context, mode: str, start_time: datetime):
    prev_status = None
    confirmed = 0

    while user_id in monitoring_sessions and monitoring_sessions[user_id]["username"] == username:
        current = await check_status(username)

        if current == prev_status:
            confirmed += 1
        else:
            confirmed = 1
            prev_status = current

        if confirmed >= 2:
            duration = format_duration(datetime.now() - start_time)
            if not current and mode == "ban":
                msg = f"@{username} | Monitoring Status : Account Banned 🚫👊 | ⏰ Time taken : {duration} 🤌"
                await context.bot.send_message(chat_id=user_id, text=msg)
                await log_bot.send_message(chat_id=ADMIN_ID, text=f"[BAN] {msg}")
                break
            elif current and mode == "unban":
                msg = f"@{username} | Monitoring Status : Account Unbanned ✅ 🤟 | ⏰ Time taken : {duration} 🤌"
                await context.bot.send_message(chat_id=user_id, text=msg)
                await log_bot.send_message(chat_id=ADMIN_ID, text=f"[UNBAN] {msg}")
                break

        await asyncio.sleep(3)

    monitoring_sessions.pop(user_id, None)

# --- Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Use /usekey <key> to activate a key.\nStart monitoring with /ban or /unban.")

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Unauthorized.")

    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /genkey <name> <days>")

    name, days = context.args[0], int(context.args[1])
    key = generate_key()
    expires = datetime.now() + timedelta(days=days)
    shared_keys[key] = {"name": name, "expires": expires}
    save_data()

    await update.message.reply_text(
        f"✅ Key: `{key}`\nName: {name}\nExpires: {expires.date()}",
        parse_mode="Markdown"
    )

async def usekey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /usekey <key>")

    key = context.args[0].strip().upper()
    if key not in shared_keys:
        return await update.message.reply_text("❌ Invalid key.")

    info = shared_keys[key]
    if info["expires"] < datetime.now():
        return await update.message.reply_text("❌ Expired key.")

    user_keys[update.effective_chat.id] = {
        "name": info["name"],
        "key": key,
        "expires": info["expires"]
    }
    save_data()
    await update.message.reply_text(f"✅ Key activated for {info['name']}")

async def key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valid, data = validate_key(update.effective_chat.id)
    if not valid:
        return await update.message.reply_text(data)

    await update.message.reply_text(
        f"🔑 Key for {data['name']}\n`{data['key']}`\nExpires: {data['expires'].date()}",
        parse_mode="Markdown"
    )

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_monitor(update, context, mode="ban")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_monitor(update, context, mode="unban")

async def start_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    valid, result = validate_key(update.effective_chat.id)
    if not valid:
        return await update.message.reply_text(result)

    if not context.args:
        return await update.message.reply_text(f"Usage: /{mode} <username>")

    username = context.args[0].lstrip("@")
    user_id = update.effective_chat.id

    monitoring_sessions[user_id] = {
        "username": username,
        "start_time": datetime.now()
    }

    await update.message.reply_text(f"👁 Started Monitoring @{username}")
    await log_bot.send_message(chat_id=ADMIN_ID, text=f"[{mode.upper()}] @{username} started by {update.effective_user.username} ({user_id})")
    asyncio.create_task(monitor_task(user_id, username, context, mode, datetime.now()))

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id in monitoring_sessions:
        del monitoring_sessions[user_id]
        await update.message.reply_text("🛑 Monitoring stopped.")
    else:
        await update.message.reply_text("⚠️ No active monitoring session.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = monitoring_sessions.get(update.effective_chat.id)
    if not session:
        return await update.message.reply_text("⚠️ No active session.")
    duration = format_duration(datetime.now() - session["start_time"])
    await update.message.reply_text(f"⏱ Monitoring @{session['username']}\nDuration: {duration}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *COMMANDS:*\n"
        "/usekey (key) : Start your subscription\n"
        "/key : Check your current key\n"
        "/ban (username) : Monitor only if account gets BANNED\n"
        "/unban (username) : Monitor only if account gets UNBANNED\n"
        "/stop : Stop monitoring\n"
        "/status : Show current monitored accounts\n\n"
        "❓ *Need help?*\n"
        "Message us at @instawatchersupport",
        parse_mode="Markdown"
    )

async def set_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("usekey", "Start your subscription"),
        BotCommand("key", "Check your current key"),
        BotCommand("ban", "Monitor only if account gets banned"),
        BotCommand("unban", "Monitor only if account gets unbanned"),
        BotCommand("stop", "Stop monitoring"),
        BotCommand("status", "Show current monitored accounts"),
        BotCommand("help", "Show help information")
    ])

async def main():
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("usekey", usekey))
    app.add_handler(CommandHandler("key", key))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))

    print("✅ Bot running...")
    await set_bot_commands(app)
    await app.run_polling()

async def main():
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("usekey", usekey))
    app.add_handler(CommandHandler("key", key))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))

    print("✅ Bot running...")
    await set_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

