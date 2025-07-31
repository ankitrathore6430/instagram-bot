
import json
import os
import time
import httpx
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import CommandHandler, MessageHandler, ApplicationBuilder, ContextTypes, filters

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# File paths
USER_FILE = "users.json"
USERNAMES_FILE = "usernames.json"

# Telegram Bot Initialization
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)


def load_json(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return default


def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


# Load users and usernames
user_ids = load_json(USER_FILE, [])
usernames = load_json(USERNAMES_FILE, {})


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in user_ids:
        user_ids.append(user.id)
        usernames[str(user.id)] = user.username or "N/A"
        save_json(USER_FILE, user_ids)
        save_json(USERNAMES_FILE, usernames)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! You have been registered.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/start - Register with the bot\n"
        "/help - Show help\n"
        "/broadcast <message> - Send a message to all users (Admin only)\n"
        "/users - Show number of users (Admin only)\n"
        "/all_users - Show all user IDs and usernames (Admin only)"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            time.sleep(0.05)
        except Exception:
            continue

    await update.message.reply_text("Broadcast sent.")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text(f"Total users: {len(user_ids)}")


async def list_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return

    user_list = [f"{uid} - @{usernames.get(str(uid), 'N/A')}" for uid in user_ids]
    message = "\n".join(user_list)
    for i in range(0, len(message), 4096):
        await update.message.reply_text(message[i:i+4096])


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that command.")


def telegram_bot_main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CommandHandler("all_users", list_all_users))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    application.run_polling()


@app.route("/")
def index():
    return "Bot is running."


if __name__ == "__main__":
    try:
        telegram_bot_main()
    except KeyboardInterrupt:
        print("Bot stopped manually.")
