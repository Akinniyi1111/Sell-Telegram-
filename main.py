import json, os, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Bot Token
BOT_TOKEN = "8266639049:AAFvQYw-ax6y94S2zH_oMg7jA2Q1Dxh6yro"
CHANNEL_LINK = "https://t.me/NR_receiver_News"

# Admin ID
ADMIN_ID = 1378825382  

# Storage paths (local for free Render plan)
USER_FILE = "users.json"
ORDER_FILE = "orders.json"

# Country Pricing
COUNTRIES = {
    "🇵🇭 +63": {"price": 0.65, "time": 1800},
    "🇸🇻 +503": {"price": 0.70, "time": 600},
    "🇮🇱 +972": {"price": 0.80, "time": 1800},
    "🇵🇸 +970": {"price": 0.85, "time": 600},
    "🇳🇿 +64": {"price": 1.10, "time": 600},
    "🇹🇷 +90": {"price": 1.15, "time": 600},
    "🇲🇩 +373": {"price": 1.15, "time": 600},
    "🇬🇱 +299": {"price": 1.45, "time": 600},
    "🇨🇿 +420": {"price": 1.65, "time": 600},
    "🇹🇼 +886": {"price": 2.10, "time": 600},
    "🇳🇱 +31": {"price": 2.15, "time": 600},
    "🇪🇸 +34": {"price": 3.40, "time": 600},
    "🇫🇷 +33": {"price": 3.50, "time": 600},
    "🇩🇪 +49": {"price": 4.00, "time": 600},
}

# Helper: Load & Save JSON
def load_data(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# Ensure storage exists
if not os.path.exists(USER_FILE):
    save_data(USER_FILE, {})
if not os.path.exists(ORDER_FILE):
    save_data(ORDER_FILE, {})

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_data(USER_FILE)

    if str(user.id) not in users:
        # First-time user → must join channel
        users[str(user.id)] = {
            "name": user.full_name,
            "balance": 0.0,
            "sold": 0,
        }
        save_data(USER_FILE, users)

        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
                    [InlineKeyboardButton("➡️ Continue to Menu", callback_data="continue_menu")]]
        await update.message.reply_text("👋 Welcome! Please join our channel to continue:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # Returning user → show phone number instructions
        await update.message.reply_text(
            "🎉 Welcome to Robot!\n\n"
            "Enter your phone number with the country code.\n"
            "Example: +62xxxxxxx\n\n"
            "Type /cap to see available countries."
        )

# /cap → Available countries
async def cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📋 *Available Countries*\n\n"
    for c, d in COUNTRIES.items():
        text += f"{c} | 💰 {d['price']}$ | ⏰ {d['time']}s\n"
    text += f"\n🌍 Total Countries: {len(COUNTRIES)}"
    await update.message.reply_text(text, parse_mode="Markdown")

# /balance → Show profile + withdraw option
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_data(USER_FILE)
    user_id = str(update.effective_user.id)
    if user_id not in users:
        await update.message.reply_text("❌ Please use /start first.")
        return

    u = users[user_id]
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (f"📋 *Your Profile*\n\n"
            f"👤 Name: {u['name']}\n"
            f"💰 Balance: ${u['balance']:.2f}\n"
            f"📦 Accounts Sold: {u['sold']}\n"
            f"⏰ Time: {now}")
    keyboard = [[InlineKeyboardButton("💵 Withdraw", callback_data="withdraw")]]
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(keyboard))

# /help
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Commands:\n/start\n/cap\n/balance\n/help")

# Handle button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "continue_menu":
        await query.edit_message_text(
            "🎉 Welcome to Robot!\n\n"
            "Enter your phone number with the country code.\n"
            "Example: +62xxxxxxx\n\n"
            "Type /cap to see available countries."
        )

    elif query.data == "withdraw":
        users = load_data(USER_FILE)
        user_id = str(query.from_user.id)
        bal = users[user_id]["balance"]

        if bal < 3:
            await query.edit_message_text("❌ Insufficient balance. Minimum withdrawal is $3.")
        else:
            await query.edit_message_text("✅ Withdrawal request sent to admin. Processing...")

# Handle numbers and OTP flow
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    users = load_data(USER_FILE)
    orders = load_data(ORDER_FILE)
    text = update.message.text.strip()

    # User sends phone number
    if text.startswith("+") and text[1:].isdigit():
        order_id = str(len(orders) + 1)
        orders[order_id] = {
            "id": order_id,
            "user_id": user_id,
            "phone": text,
            "status": "pending"
        }
        save_data(ORDER_FILE, orders)

        await update.message.reply_text("✅ Processing please wait...")

        # Notify Admin
        keyboard = [
            [InlineKeyboardButton("✅ Request OTP", callback_data=f"admin_request_{order_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"admin_reject_{order_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 New Sell Request\n👤 {user.full_name}\n📱 {text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # User sending OTP after admin requests
    else:
        pending_orders = [o for o in orders.values()
                          if o["user_id"] == user_id and o["status"] == "otp_requested"]
        if pending_orders:
            order = pending_orders[0]
            order_id = order["id"]

            orders[order_id]["otp"] = text
            orders[order_id]["status"] = "otp_submitted"
            save_data(ORDER_FILE, orders)

            keyboard = [
                [InlineKeyboardButton("🔄 Retry", callback_data=f"admin_retry_{order_id}")],
                [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{order_id}")],
                [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}")]
            ]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔐 OTP for Order {order_id}\n📱 {order['phone']}\nOTP: {text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await update.message.reply_text("✅ OTP received. Wait for admin review.")

# Admin actions
async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    orders = load_data(ORDER_FILE)
    users = load_data(USER_FILE)
    data = query.data

    if not data.startswith("admin_"):
        return

    order_id = data.split("_")[2]
    order = orders[order_id]
    user_id = order["user_id"]

    if data.startswith("admin_request_"):
        orders[order_id]["status"] = "otp_requested"
        save_data(ORDER_FILE, orders)
        await context.bot.send_message(chat_id=user_id, text="🇹🇼 Enter the code sent to the number")
        await query.edit_message_text(f"✅ OTP requested for order {order_id}")

    elif data.startswith("admin_reject_"):
        orders[order_id]["status"] = "rejected"
        save_data(ORDER_FILE, orders)
        await context.bot.send_message(chat_id=user_id, text="❌ Your sell request was rejected.")
        await query.edit_message_text(f"❌ Order {order_id} rejected")

    elif data.startswith("admin_approve_"):
        price = COUNTRIES.get(order["phone"][:4], {"price": 1})["price"]
        users[user_id]["balance"] += price
        users[user_id]["sold"] += 1
        save_data(USER_FILE, users)
        orders[order_id]["status"] = "completed"
        save_data(ORDER_FILE, orders)
        await context.bot.send_message(chat_id=user_id, text=f"✅ Deal approved! ${price} credited.")
        await query.edit_message_text(f"✅ Order {order_id} approved")

    elif data.startswith("admin_retry_"):
        orders[order_id]["status"] = "otp_requested"
        save_data(ORDER_FILE, orders)
        await context.bot.send_message(chat_id=user_id, text="🔄 Enter another OTP, the previous expired.")
        await query.edit_message_text(f"🔄 Retry OTP for order {order_id}")

# Main
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cap", cap))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(admin_actions))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot running with polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
