import asyncio
import random
import string
import json
import os
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from playwright.async_api import async_playwright

# ========== YOUR SETTINGS ==========
BOT_TOKEN = "8010738634:AAFoGbZW9Heaz-mtQk8qyHTc1N8m3eUkzuM"
ADMIN_ID = 6684244590
DATA_FILE = "data.json"
# ===================================

user_keys = {}
shared_keys = {}
monitoring_sessions = {}

# Load data from file
def load_data():
    global user_keys, shared_keys
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            user_keys.update({
                int(k): {
                    "name": v["name"],
                    "key": v["key"],
                    "expires": datetime.fromisoformat(v["expires"]),
                    "followers": v.get("followers", "N/A")
                } for k, v in data.get("user_keys", {}).items()
            })
            shared_keys.update({
                k: {
                    "name": v["name"],
                    "expires": datetime.fromisoformat(v["expires"])
                } for k, v in data.get("shared_keys", {}).items()
            })

# Save data to file
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "user_keys": {
                str(k): {
                    "name": v["name"],
                    "key": v["key"],
                    "expires": v["expires"].isoformat(),
                    "followers": v.get("followers", "N/A")
                } for k, v in user_keys.items()
            },
            "shared_keys": {
                k: {
                    "name": v["name"],
                    "expires": v["expires"].isoformat()
                } for k, v in shared_keys.items()
            }
        }, f, indent=2)

# Generate a unique 10-character key
def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# Validate user key
def validate_key(user_id):
    data = user_keys.get(user_id)
    if not data:
        return False, "❌ You don’t have an active key. Use /usekey <key> to activate one."
    if data['expires'] < datetime.now():
        return False, "❌ Your key has expired."
    return True, data

# Format duration with seconds
def format_duration(td: timedelta):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours} hr {minutes} mins {seconds} secs"
    elif minutes:
        return f"{minutes} mins {seconds} secs"
    else:
        return f"{seconds} secs"

# Monitor account
async def monitor_account(user_id: int, username: str, context):
    prev_status = monitoring_sessions[user_id]["status"]
    first_check = True
    consistent_checks = 0
    while True:
        if user_id not in monitoring_sessions:
            break
        status, followers = await check_instagram_status(username)

        if followers in ["N/A", "0"]:
            followers = user_keys[user_id].get("followers", "0")
        else:
            user_keys[user_id]["followers"] = followers
            save_data()

        if first_check:
            first_check = False
        elif status != prev_status:
            consistent_checks += 1
            if consistent_checks < 2:
                await asyncio.sleep(5)
                continue
            duration = datetime.now() - monitoring_sessions[user_id]["start_time"]
            name = user_keys[user_id]['name']
            saved_followers = user_keys[user_id].get("followers", followers)
            if not status:
                msg = f"@{username} | Monitoring Status : Account Banned 🚫👊 | Followers count : {saved_followers} | ⏰ Time taken : {format_duration(duration)} 🤌"
            else:
                msg = f"@{username} | Monitoring Status : Account Unbanned ✅ 🤟 | Followers count : {followers} | ⏰ Time taken : {format_duration(duration)} 🤌"
            await context.bot.send_message(chat_id=user_id, text=msg)
            del monitoring_sessions[user_id]
            break
        else:
            consistent_checks = 0
        await asyncio.sleep(5)
