#!/usr/bin/env python3
"""
Instagram Video Downloader Telegram Bot (Webhook & GitHub Backup Version)

This bot uses webhooks and automatically backs up user data to a private
GitHub repository to prevent data loss on redeployment.
"""

import logging
import re
import httpx
import asyncio
import os
import base64
from telegram import Update, error
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from flask import Flask, request

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BOT_TOKEN = "8042117650:AAFlx2qNx868SKTZj0hRX_eDQ5NzqdCot_o"
WEBHOOK_URL = "https://instagram-bot-ulut.onrender.com"
API_ENDPOINT = "https://apihut.in/api/download/videos"
API_KEY = "8c5543b2-d8de-44f8-85c8-47b981e86315"
ADMIN_ID = 745211839
USER_IDS_FILE = "user_ids.txt"

# --- NEW GITHUB BACKUP CONFIG ---
# ⚠️ WARNING: Storing tokens directly in code is NOT SAFE and NOT RECOMMENDED.
# If this code is public, your token will be stolen and automatically blocked by GitHub.
# Use Render's Environment Variables for better security.
GITHUB_TOKEN = "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"
GITHUB_USERNAME = "ankitrathore6430"
GITHUB_REPO = "instagram-bot"


# Global variable to store the count of successfully downloaded videos
download_count = 0

# --- NEW GITHUB FUNCTIONS ---

async def backup_to_github():
    """Reads the user_ids.txt file and uploads it to the GitHub repo."""
    if not all([GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_REPO]):
        logger.warning("GitHub credentials not set. Skipping backup.")
        return

    try:
        with open(USER_IDS_FILE, "r") as f:
            content = f.read()
        
        if not content.strip():
            logger.info("user_ids.txt is empty. Skipping backup.")
            return

        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{USER_IDS_FILE}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        
        async with httpx.AsyncClient() as client:
            # First, try to get the file to see if it exists and get its SHA
            sha = None
            try:
                get_response = await client.get(api_url, headers=headers)
                if get_response.status_code == 200:
                    sha = get_response.json()["sha"]
            except Exception:
                pass # File might not exist, which is fine

            # Prepare the data for upload
            content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            data = {
                "message": "Automated user data backup",
                "content": content_base64,
            }
            if sha:
                data["sha"] = sha # Add SHA if we are updating the file

            # Create or update the file
            put_response = await client.put(api_url, headers=headers, json=data)
            
            if put_response.status_code in [200, 201]:
                logger.info("Successfully backed up user_ids.txt to GitHub.")
            else:
                logger.error(f"Failed to backup to GitHub. Status: {put_response.status_code}, Response: {put_response.text}")

    except FileNotFoundError:
        logger.warning("user_ids.txt not found for backup.")
    except Exception as e:
        logger.error(f"An error occurred during GitHub backup: {e}")

async def restore_from_github():
    """Downloads user_ids.txt from GitHub on startup to restore data."""
    if not all([GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_REPO]):
        logger.warning("GitHub credentials not set. Skipping restore.")
        return set()

    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{USER_IDS_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers)
        
        if response.status_code == 200:
            content_base64 = response.json()["content"]
            content = base64.b64decode(content_base64).decode('utf-8')
            
            with open(USER_IDS_FILE, "w") as f:
                f.write(content)
            
            logger.info("Successfully restored user_ids.txt from GitHub.")
            # Return the set of user IDs from the restored file
            return set(int(line.strip()) for line in content.splitlines() if line.strip())
        else:
            logger.warning("No backup file found on GitHub. Starting with an empty user list.")
            return set()
    except Exception as e:
        logger.error(f"Failed to restore from GitHub: {e}")
        return set()

# Modified save_user_ids to trigger backup
def save_user_ids():
    with open(USER_IDS_FILE, "w") as f:
        for user_id in user_ids:
            f.write(f"{user_id}\n")
    # Schedule the backup to run in the background
    asyncio.create_task(backup_to_github())


# Initialize user_ids as a global variable to be populated by restore_from_github
user_ids = set()

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_ids:
        user_ids.add(user_id)
        save_user_ids() # This will now trigger the backup
    
    welcome_message = """
🎬 *Instagram Video Downloader Bot*

Welcome! I can help you download Instagram videos.

📋 *How to use:*
1. Send me an Instagram video post link
2. I'll download the video for you
3. Enjoy your video!

⚠️ *Note:* I can only download public content. Private posts won't work.

Any Issue Contact Admin @AnkitRathore

Just send me a link to get started! 🚀
    """
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)

async def download_instagram_video(url: str) -> dict:
    headers = {"X-Avatar-Key": API_KEY, "Content-Type": "application/json"}
    payload = {"video_url": url, "type": "instagram"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(API_ENDPOINT, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def is_valid_instagram_url(url: str) -> bool:
    INSTAGRAM_URL_PATTERN = re.compile(
    r'https?://(www\.)?(instagram\.com|instagr\.am)/(p|reel|tv)/[A-Za-z0-9_-]+/?(?:\?.*)?'
    )
    return bool(INSTAGRAM_URL_PATTERN.match(url))

download_queue = asyncio.Queue()

async def download_worker():
    global download_count
    while True:
        update, context, processing_message, message_text = await download_queue.get()
        try:
            api_response = await download_instagram_video(message_text)
            if "error" in api_response:
                await processing_message.edit_text(f"❌ *Error occurred:*\n{api_response['error']}", parse_mode=ParseMode.MARKDOWN)
                continue
            video_url = None
            data = api_response.get("data") or api_response.get("message", {}).get("data") or api_response
            if isinstance(data, list) and len(data) > 0:
                video_url = data[0].get("url")
            elif isinstance(data, dict):
                video_url = data.get("url") or data.get("video_url")
            if not video_url:
                await processing_message.edit_text("❌ *Could not extract video URL*", parse_mode=ParseMode.MARKDOWN)
                continue
            await processing_message.edit_text("📥 Downloading video...")
            async with httpx.AsyncClient() as client:
                video_response = await client.get(video_url, follow_redirects=True, timeout=300)
            video_response.raise_for_status()
            await update.message.reply_video(video=video_response.content, caption="✅ *Video downloaded successfully!*", parse_mode=ParseMode.MARKDOWN)
            await processing_message.delete()
            download_count += 1
        except Exception as e:
            logger.error(f"Error processing {message_text}: {str(e)}")
            await processing_message.edit_text(f"❌ *An unexpected error occurred*", parse_mode=ParseMode.MARKDOWN)
        finally:
            download_queue.task_done()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_ids:
        user_ids.add(user_id)
        save_user_ids() # This will now trigger the backup
    message_text = update.message.text.strip()
    if not is_valid_instagram_url(message_text):
        await update.message.reply_text("❌ *Invalid Instagram URL*", parse_mode=ParseMode.MARKDOWN)
        return
    processing_message = await update.message.reply_text("⏳ Processing your request...")
    await download_queue.put((update, context, processing_message, message_text))

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    message = " ".join(context.args)
    if not message: return
    success_count, fail_count = 0, 0
    users_to_remove = []
    for user_id in list(user_ids):
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            success_count += 1
        except error.Forbidden:
            users_to_remove.append(user_id)
            fail_count += 1
        except Exception:
            fail_count += 1
    if users_to_remove:
        for user_id in users_to_remove:
            user_ids.discard(user_id)
        save_user_ids() # Save and backup the updated list
    await update.message.reply_text(f"Broadcast complete: Sent to {success_count}, Failed for {fail_count}.")

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id == ADMIN_ID:
        await update.message.reply_text(f"Total registered users: {len(user_ids)}")

async def show_download_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id == ADMIN_ID:
        await update.message.reply_text(f"Total videos downloaded: {download_count}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning(f'Update "{update}" caused error "{context.error}"')

# --- APPLICATION SETUP ---
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("broadcast", broadcast))
application.add_handler(CommandHandler("showusers", show_users))
application.add_handler(CommandHandler("totaldownloads", show_download_count))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_error_handler(error_handler)

app = Flask(__name__)
@app.route("/")
def index(): return "Bot is running with webhook and GitHub backup!"
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook_handler():
    update_data = await request.get_json()
    if update_data:
        update = Update.de_json(data=update_data, bot=application.bot)
        await application.process_update(update)
    return "ok", 200

async def main():
    global user_ids
    # Restore users from GitHub at startup
    user_ids = await restore_from_github()
    
    asyncio.create_task(download_worker())
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}", allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook set and bot is ready with {len(user_ids)} users restored.")
    print(f"🤖 Bot ready! {len(user_ids)} users restored from GitHub.")

if __name__ == "instagram_bot":
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(main())
    else:
        asyncio.run(main())