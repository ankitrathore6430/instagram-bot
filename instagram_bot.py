#!/usr/bin/env python3
"""
Instagram Video Downloader Telegram Bot

This bot allows users to download Instagram videos by sending a video post link.
It uses the Instagram downloader API from apihut.in to fetch video download links.

Requirements:
- python-telegram-bot
- requests
- flask

Usage:
1. Send /start to get instructions
2. Send an Instagram video post link
3. Receive the downloaded video
"""

import logging
import re
import httpx
import asyncio
import threading
from telegram import Update, error
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from flask import Flask

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8042117650:AAH1aVXniFrVPdfN9-G9_EerhExWpSIG8Qk"
API_ENDPOINT = "https://apihut.in/api/download/videos"
API_KEY = "8c5543b2-d8de-44f8-85c8-47b981e86315"

ADMIN_ID = 745211839  # Replace with your Telegram user ID

USER_IDS_FILE = "user_ids.txt"
# Global variable to store the count of successfully downloaded videos
download_count = 0

def load_user_ids():
    try:
        with open(USER_IDS_FILE, "r") as f:
            # Filter out empty lines before converting to an integer
            return set(int(line.strip()) for line in f if line.strip())
    except FileNotFoundError:
        return set()

def save_user_ids():
    with open(USER_IDS_FILE, "w") as f:
        for user_id in user_ids:
            f.write(f"{user_id}\n")

# In-memory storage for user IDs (for simplicity)
# For a production bot, consider using a database
user_ids = load_user_ids()

# Instagram URL pattern
INSTAGRAM_URL_PATTERN = re.compile(
    r'https?://(www\.)?(instagram\.com|instagr\.am)/(p|reel|tv)/[A-Za-z0-9_-]+/?(?:\?.*)?'
)

# Flask application for uptime monitoring
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    # Add user ID to the list when the /start command is used
    user_id = update.message.from_user.id
    user_ids.add(user_id)
    save_user_ids()
    
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
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )

async def download_instagram_video(url: str) -> dict:
    """
    Download Instagram video using the API.
    
    Args:
        url (str): Instagram video URL
        
    Returns:
        dict: API response containing video download link or error
    """
    headers = {
        "X-Avatar-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "video_url": url,
        "type": "instagram"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                API_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=60
            )
        
        response.raise_for_status()
        return response.json()
        
    except httpx.TimeoutException:
        return {"error": "Request timeout. Please try again."}
    except httpx.ConnectError:
        return {"error": "Connection error. Please check your internet connection."}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def is_valid_instagram_url(url: str) -> bool:
    """
    Check if the provided URL is a valid Instagram URL.
    
    Args:
        url (str): URL to validate
        
    Returns:
        bool: True if valid Instagram URL, False otherwise
    """
    return bool(INSTAGRAM_URL_PATTERN.match(url))

download_queue = asyncio.Queue()

async def download_worker():
    global download_count
    while True:
        update, context, processing_message, message_text = await download_queue.get()
        try:
            api_response = await download_instagram_video(message_text)
            if "error" in api_response:
                await processing_message.edit_text(
                    f"❌ *Error occurred:*\n{api_response['error']}\n\n"
                    "Please try again or check if the post is public.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            video_url = None
            if "data" in api_response:
                data = api_response["data"]
                if isinstance(data, list) and len(data) > 0:
                    video_url = data[0].get("url") or data[0].get("download_url")
                elif isinstance(data, dict):
                    video_url = data.get("url") or data.get("download_url") or data.get("video_url")
            elif "message" in api_response and "data" in api_response["message"]:
                data = api_response["message"]["data"]
                if isinstance(data, list) and len(data) > 0:
                    video_url = data[0].get("url") or data[0].get("download_url")
                elif isinstance(data, dict):
                    video_url = data.get("url") or data.get("download_url") or data.get("video_url")
            elif "url" in api_response:
                video_url = api_response["url"]
            elif "download_url" in api_response:
                video_url = api_response["download_url"]

            if not video_url:
                await processing_message.edit_text(
                    "❌ *Could not extract video URL*\n\n"
                    "The API response doesn't contain a valid video download link.\n"
                    "This might happen if:\n"
                    "• The post is private\n"
                    "• The post doesn't contain a video\n"
                    "• The post has been deleted",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            await processing_message.edit_text(
                "📥 Downloading video...\nThis may take a moment depending on the video size."
            )

            async with httpx.AsyncClient() as client:
                video_response = await client.get(video_url, follow_redirects=True, timeout=300)
            video_response.raise_for_status()

            await update.message.reply_video(
                video=video_response.content,
                caption="✅ *Video downloaded successfully!*\n\nEnjoy your Instagram video! 🎬",
                parse_mode=ParseMode.MARKDOWN
            )
            await processing_message.delete()
            
            download_count += 1

        except httpx.RequestError as e:
            await processing_message.edit_text(
                f"❌ *Failed to download video from URL*\n\n"
                f"Error: {str(e)}\n\n"
                "This might happen if:\n"
                "• The video file is too large\n"
                "• The video format is not supported\n"
                "• Network connection issues",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error processing Instagram URL {message_text}: {str(e)}")
            await processing_message.edit_text(
                f"❌ *Unexpected error occurred*\n\n"
                f"Error: {str(e)}\n\n"
                "Please try again later or contact support if the issue persists.",
                parse_mode=ParseMode.MARKDOWN
            )
        finally:
            download_queue.task_done()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_ids.add(user_id)
    save_user_ids()

    message_text = update.message.text.strip()

    if not is_valid_instagram_url(message_text):
        await update.message.reply_text(
            "❌ *Invalid Instagram URL*\n\n"
            "Please send a valid Instagram video post link.\n\n"
            "*Examples:*\n"
            "• https://instagram.com/p/ABC123/\n"
            "• https://instagram.com/reel/XYZ789/\n"
            "• https://instagram.com/tv/DEF456/",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    processing_message = await update.message.reply_text(
        "⏳ Processing your request...\nPlease wait while I download the video."
    )
    await download_queue.put((update, context, processing_message, message_text))

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.warning(f'Update "{update}" caused error "{context.error}"')
    
    if update and update.message:
        await update.message.reply_text(
            "❌ *An error occurred while processing your request.*\n\n"
            "Please try again later. If the problem persists, contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Broadcast a message to all users. Only accessible by the admin.
    """
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Please provide a message to broadcast. Usage: /broadcast <your message>")
        return

    message_to_broadcast = " ".join(context.args)
    
    # Create a list of tasks for sending messages concurrently
    tasks = [
        context.bot.send_message(
            chat_id=user_id,
            text=message_to_broadcast
        ) for user_id in user_ids
    ]
    
    # Run all tasks and collect results, ignoring exceptions
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = 0
    fail_count = 0
    users_to_remove = []

    for user_id, result in zip(user_ids, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to send broadcast message to user {user_id}: {result}")
            fail_count += 1
            if isinstance(result, error.Forbidden):
                users_to_remove.append(user_id)
        else:
            success_count += 1
            
    # Remove users who blocked the bot and save the updated list
    for user_id in users_to_remove:
        user_ids.discard(user_id)
        
    save_user_ids()
    
    await update.message.reply_text(
        f"Broadcast complete!\nSuccessfully sent to {success_count} users.\nFailed to send to {fail_count} users."
    )

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Shows a list of all user IDs and usernames to the admin.
    """
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    message = "*Registered Users:*\n\n"
    
    for user_id in user_ids:
        try:
            chat = await context.bot.get_chat(user_id)
            user_info = f"- ID: `{user_id}`"
            if chat.username:
                user_info += f" | Username: @{chat.username}"
            elif chat.first_name:
                user_info += f" | Name: {chat.first_name}"
            
            message += f"{user_info}\n"
        except Exception as e:
            logger.error(f"Failed to get chat info for user {user_id}: {e}")
            message += f"- ID: `{user_id}` (Info unavailable)\n"
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN
    )

async def show_download_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Shows the total number of videos downloaded to the admin.
    """
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    await update.message.reply_text(f"Total videos downloaded: {download_count}")

def main() -> None:
    """Start the bot."""
    # Start the Flask server in a separate thread
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("showusers", show_users))
    application.add_handler(CommandHandler("totaldownloads", show_download_count))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting Instagram Video Downloader Bot...")
    print("🤖 Instagram Video Downloader Bot is starting...")
    print("Press Ctrl+C to stop the bot")

    async def post_init(application: Application) -> None:
        asyncio.create_task(download_worker())

    application.post_init = post_init
    
    # Run the bot until the user presses Ctrl-C
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user. Saving user IDs...")
        save_user_ids()
        logger.info("User IDs saved. Exiting.")


if __name__ == '__main__':
    main()
