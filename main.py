import json, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Bot Token
BOT_TOKEN = "8266639049:AAFvQYw-ax6y94S2zH_oMg7jA2Q1Dxh6yro"
CHANNEL_LINK = "https://t.me/NR_receiver_News"
SUPPORT_USERNAME = "https://t.me/TG_BUYER_NR"

# Admin ID (replace with your Telegram ID)
ADMIN_ID = 1378825382  

# Storage paths (Render Disk)
USER_FILE = "/mnt/data/users.json"
ORDER_FILE = "/mnt/data/orders.json"

# Country Pricing
COUNTRIES = {
    "malaysia": {"code": "+60", "price": 0.65, "flag": "🇲🇾"},
    "israel": {"code": "+972", "price": 0.87, "flag": "🇮🇱"}
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
        users[str(user.id)] = {
            "name": user.full_name,
            "balance": 0.0,
            "referrals": 0,
            "sold": 0
        }
        save_data(USER_FILE, users)

    keyboard = [
        [InlineKeyboardButton("📋 My Profile", callback_data="profile")],
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("🆘 Contact Support", url=SUPPORT_USERNAME)],
        [InlineKeyboardButton("👥 Referral", callback_data="referral")],
        [InlineKeyboardButton("💼 Sell Account", callback_data="sell")],
        [InlineKeyboardButton("📂 Pending Orders", callback_data="pending")]
    ]
    await update.message.reply_text(
        f"👋 Welcome to *NR Receiver Bot*!\n\nChoose an option below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# Button Handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = load_data(USER_FILE)
    orders = load_data(ORDER_FILE)
    user_id = str(query.from_user.id)

    if query.data == "profile":
        u = users[user_id]
        text = (f"📋 *Your Profile*\n\n"
                f"👤 Name: {u['name']}\n"
                f"💰 Balance: ${u['balance']:.2f}\n"
                f"👥 Referrals: {u['referrals']}\n"
                f"📦 Accounts Sold: {u['sold']}")
        await query.edit_message_text(text, parse_mode="Markdown")

    elif query.data == "referral":
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={user_id}"
        await query.edit_message_text(f"👥 *Your Referral Link:*\n{link}", parse_mode="Markdown")

    elif query.data == "sell":
        keyboard = [
            [InlineKeyboardButton(f"{COUNTRIES['malaysia']['code']} Malaysia {COUNTRIES['malaysia']['price']}$ {COUNTRIES['malaysia']['flag']}", callback_data="sell_malaysia")],
            [InlineKeyboardButton(f"{COUNTRIES['israel']['code']} Israel {COUNTRIES['israel']['price']}$ {COUNTRIES['israel']['flag']}", callback_data="sell_israel")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")]
        ]
        await query.edit_message_text("💼 Select a country account to sell:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sell_"):
        country = query.data.split("_")[1]
        context.user_data["selling_country"] = country
        await query.edit_message_text("📱 Send me the *phone number* of the account you want to sell:", parse_mode="Markdown")

    elif query.data == "pending":
        pending_orders = [o for o in orders.values() if o["user_id"] == user_id and o["status"] != "completed"]
        if not pending_orders:
            await query.edit_message_text("📂 You have no pending orders.")
        else:
            text = "📂 *Your Pending Orders:*\n\n"
            for o in pending_orders:
                text += f"ID: {o['id']} | {o['country']} | {o['phone']} | Status: {o['status']}\n"
            await query.edit_message_text(text, parse_mode="Markdown")

    elif query.data == "back":
        await start(update, context)

# Handle Phone Numbers & OTP Flow
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    users = load_data(USER_FILE)
    orders = load_data(ORDER_FILE)

    # User is sending phone number
    if "selling_country" in context.user_data:
        phone = update.message.text.strip()
        country = context.user_data["selling_country"]

        # Check if phone already sold
        for order in orders.values():
            if order["phone"] == phone and order["status"] == "completed":
                await update.message.reply_text("❌ This number has already been sold.")
                return

        # Save new order
        order_id = str(len(orders) + 1)
        orders[order_id] = {
            "id": order_id,
            "user_id": user_id,
            "phone": phone,
            "country": country,
            "status": "pending"
        }
        save_data(ORDER_FILE, orders)

        await update.message.reply_text("✅ Processing... OTP will be requested within 10 minutes.\nStay active to avoid rejection.")

        # Notify Admin
        keyboard = [
            [InlineKeyboardButton("✅ Request OTP", callback_data=f"admin_request_{order_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 *New Sell Request*\n\n👤 User: {user.full_name}\n📱 Phone: {phone}\n🌍 Country: {country}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        del context.user_data["selling_country"]

# TODO: Admin OTP & Approval Flow Handlers (to be added next)

# Main
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
