from datetime import datetime
import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import keep_alive
keep_alive.keep_alive()


username = "jai_siya_ram_63"
password = "Ankit6430"
#!/usr/bin/env python3
"""
Instagram Video Downloader Telegram Bot

This bot allows users to download Instagram videos by sending a video post link.
It uses the Instagram downloader API from apihut.in to fetch video download links.

Requirements:
- python-telegram-bot
- requests

Usage:
1. Send /start to get instructions
2. Send an Instagram video post link
3. Receive the downloaded video
"""

import logging
import re
import httpx
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8042117650:AAEZrMNPkf10zm1dWJWeZdGYb6i51kgkYfI"
API_ENDPOINT = "https://apihut.in/api/download/videos"
API_KEY = "8c5543b2-d8de-44f8-85c8-47b981e86315"

ADMIN_ID = 745211839  # Replace with your Telegram user ID

USER_IDS_FILE = "user_ids.txt"
USER_STATS_FILE = "user_stats.json"

def load_user_ids():
    try:
        with open(USER_IDS_FILE, "r") as f:
            return set(int(line.strip()) for line in f)
    except FileNotFoundError:
        return set()

def save_user_ids():
    with open(USER_IDS_FILE, "w") as f:
        for user_id in user_ids:
            f.write(f"{user_id}\n")

# In-memory storage for user IDs (for simplicity)
# For a production bot, consider using a database
user_ids = load_user_ids()


def update_user_stats(user: object):
    user_id = user.id
    try:
        with open(USER_STATS_FILE, "r") as f:
            stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        stats = {}

    if str(user_id) not in stats:
        stats[str(user_id)] = {
            "joined": datetime.utcnow().strftime("%Y-%m-%d"),
            "username": user.username,
            "first_name": user.first_name
        }

        with open(USER_STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)

def add_user_id(user_id: int):
    if user_id not in user_ids:
        update_user_stats(update.effective_user)
        user_ids.add(user_id)
        with open(USER_IDS_FILE, "a") as f:
            f.write(f"{user_id}\n")


# Instagram URL pattern
INSTAGRAM_URL_PATTERN = re.compile(
    r'https?://(www\.)?(instagram\.com|instagr\.am)/(p|reel|tv)/[A-Za-z0-9_-]+/?(?:\?.*)?'
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
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
    
    add_user_id(update.effective_user.id)
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


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin panel interface."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to access the admin panel.")
        return

    total_users = len(user_ids)
    message = f"🛠️ *Admin Panel*\n\n👥 Total Users: *{total_users}*"

    keyboard = [
        [InlineKeyboardButton("📢 Send Broadcast", callback_data="send_broadcast")],
        [InlineKeyboardButton("📄 Download User List", callback_data="download_users")],
        [InlineKeyboardButton("👥 Show All Users", callback_data="show_users")],
        [InlineKeyboardButton("📈 User Stats", callback_data="user_stats")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    """Admin panel interface."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to access the admin panel.")
        return

    total_users = len(user_ids)
    message = f"🛠️ *Admin Panel*\n\n👥 Total Users: *{total_users}*"

    keyboard = [
        [InlineKeyboardButton("📢 Send Broadcast", callback_data="send_broadcast")],
        [InlineKeyboardButton("📄 Download User List", callback_data="download_users")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


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
    success_count = 0
    fail_count = 0

    for user_id in list(user_ids):  # Iterate over a copy to avoid issues if set changes
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_broadcast)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast message to user {user_id}: {e}")
            fail_count += 1
            user_ids.discard(user_id) # Remove problematic user ID
            save_user_ids() # Save updated user_ids

    await update.message.reply_text(
        f"Broadcast complete!\nSuccessfully sent to {success_count} users.\nFailed to send to {fail_count} users."
    )










def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CommandHandler("broadcast", broadcast))
application.add_handler(CommandHandler("admin", admin_panel))
application.add_handler(CallbackQueryHandler(handle_admin_buttons))
application.add_handler(CommandHandler("help", help_command))
    
    # Register error handler
application.add_error_handler(error_handler)
    
    # Start the bot
if __name__ == "__main__":
    logger.info("Starting Instagram Video Downloader Bot...")
    print("🤖 Instagram Video Downloader Bot is starting...")
    print("Press Ctrl+C to stop the bot")
    application.run_polling(post_init=post_init)

    async def post_init(application: Application) -> None:
        asyncio.create_task(download_worker())

    application.post_init = post_init
    
    # Run the bot until the user presses Ctrl-C
    try:
    except KeyboardInterrupt:
        save_user_ids()


if __name__ == '__main__':
    main()





async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast a message to all users (admin only)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Please provide a message to broadcast.\nUsage: /broadcast Your message here")
        return

    message = "📢 *Broadcast Message:*\n" + " ".join(context.args)
    sent_count = 0

    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message, parse_mode=ParseMode.MARKDOWN)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to send message to {uid}: {e}")

    await update.message.reply_text(f"✅ Broadcast sent to {sent_count} users.")


async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses from admin panel."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized access.")
        return

    if query.data == "show_users":
        try:
            with open(USER_STATS_FILE, "r") as f:
                stats = json.load(f)
        except Exception:
            stats = {}

        if not stats:
            await query.edit_message_text("🚫 No active users found.")
            return

        user_lines = []
        for uid, data in stats.items():
            name = data.get("username")
            if name:
                label = f"@{name}"
            else:
                label = data.get("first_name", "Unknown")
            user_lines.append(f"👤 {label} ({uid})")

        user_text = "\n".join(user_lines)
        message = f"👥 *Active Users ({len(stats)}):*\n\n{user_text}"
        await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)

    elif query.data == "user_stats":
        try:
            with open(USER_STATS_FILE, "r") as f:
                stats = json.load(f)
        except Exception:
            stats = {}

        total = len(stats)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        new_today = sum(1 for u in stats.values() if u.get("joined") == today)
        first_join = min((u.get("joined") for u in stats.values() if "joined" in u), default="N/A")

        msg = f"📈 *User Stats*\n\n👥 Total: *{total}*\n🆕 Joined Today: *{new_today}*\n📅 First User: *{first_join}*"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)


    elif query.data == "download_users":
        await query.edit_message_text("📄 Downloading users is not yet implemented.")
    elif query.data == "send_broadcast":
        await query.edit_message_text("📢 Please use /broadcast <message> to send a message.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a list of available commands."""
    help_text = """📖 *Bot Commands*

👤 *User Commands*
/start - Welcome and instructions
/help - Show this help message
🔗 Send any public Instagram video/reel/post URL to download

👑 *Admin Commands*
/broadcast <message> - Send a message to all users
/admin - Open the admin panel
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)