import os
import json
import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ================== CONFIG ==================
BOT_TOKEN = "8266639049:AAFvQYw-ax6y94S2zH_oMg7jA2Q1Dxh6yro"
CHANNEL_LINK = "https://t.me/NR_receiver_News"

# Two admins
ADMIN_IDS = {1378825382, 7780307520}

USER_FILE = "users.json"
ORDER_FILE = "orders.json"
WITHDRAW_FILE = "withdraws.json"

# ================== COUNTRY PRICES ==================
PRICE_MAP = {
    "+886": 2.10, "+46": 1.60, "+31": 2.10, "+34": 3.10, "+48": 1.40,
    "+853": 1.55, "+40": 1.55, "+30": 1.70, "+994": 1.20, "+216": 0.60,
    "+49": 3.10, "+43": 1.60, "+420": 1.65, "+353": 1.55, "+351": 1.80,
    "+505": 0.85, "+595": 1.00, "+63": 0.63, "+970": 0.85, "+972": 0.80,
    "+593": 0.90, "+966": 1.95
}

CAP_TEXT = """📋 Available Countries

🇹🇼 +886 | Taiwan | 💰 2.10$
🇳🇴 +46  | Norway | 💰 1.60$
🇳🇱 +31  | Netherlands | 💰 2.10$
🇪🇸 +34  | Spain | 💰 3.10$
🇵🇱 +48  | Poland | 💰 1.40$
🇲🇴 +853 | Macau | 💰 1.55$
🇷🇴 +40  | Romania | 💰 1.55$
🇬🇷 +30  | Greece | 💰 1.70$
🇦🇿 +994 | Azerbaijan | 💰 1.20$
🇹🇳 +216 | Tunisia | 💰 0.60$
🇩🇪 +49  | Germany | 💰 3.10$
🇦🇹 +43  | Austria | 💰 1.60$
🇨🇿 +420 | Czech Republic | 💰 1.65$
🇮🇪 +353 | Ireland | 💰 1.55$
🇵🇹 +351 | Portugal | 💰 1.80$
🇳🇮 +505 | Nicaragua | 💰 0.85$
🇵🇾 +595 | Paraguay | 💰 1.00$
🇵🇭 +63  | Philippines | 💰 0.63$
🇵🇸 +970 | Palestine | 💰 0.85$
🇮🇱 +972 | Israel | 💰 0.80$
🇪🇨 +593 | Ecuador | 💰 0.90$
🇸🇦 +966 | Saudi Arabia | 💰 1.95$

🌍 Total Countries: 22
"""

# ================== STORAGE HELPERS ==================
def ensure_file(path: str):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)

def load_json(path: str):
    ensure_file(path)
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_json(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

ensure_file(USER_FILE)
ensure_file(ORDER_FILE)
ensure_file(WITHDRAW_FILE)

# ================== UTILS ==================
def utc_now_str():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def get_price_for_number(number: str) -> float:
    number = number.strip()
    best_price = 0.0
    best_len = -1
    for prefix, price in PRICE_MAP.items():
        if number.startswith(prefix) and len(prefix) > best_len:
            best_len = len(prefix)
            best_price = price
    return best_price

async def send_to_admins(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, reply_markup=reply_markup)
        except Exception:
            pass

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_json(USER_FILE)
    uid = str(update.effective_user.id)
    if uid not in users:
        users[uid] = {
            "name": update.effective_user.full_name,
            "balance": 0.0,
            "sold": 0
        }
        save_json(USER_FILE, users)
        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("➡️ Continue to Menu", callback_data="continue_menu")]
        ]
        await update.message.reply_text("👋 Welcome! Please join our channel first:", reply_markup=InlineKeyboardMarkup(kb))
        return
    await update.message.reply_text(
        "🎉 Welcome to Robot!\n\n"
        "Enter your phone number with the country code.\n"
        "Example: +62xxxxxxx\n\n"
        "Type /cap to see available countries."
    )

async def cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CAP_TEXT)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_json(USER_FILE)
    uid = str(update.effective_user.id)
    if uid not in users:
        await update.message.reply_text("❌ Please use /start first.")
        return
    u = users[uid]
    text = (f"👤 Name: {u['name']}\n"
            f"💰 Balance: ${u['balance']:.2f}\n"
            f"📱 Accounts Sold: {u['sold']}\n"
            f"🕒 Time: {utc_now_str()}")
    kb = [[InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = load_json(ORDER_FILE)
    uid = str(update.effective_user.id)
    found = None
    for oid, od in list(orders.items()):
        if od.get("user_id") == uid and od.get("status") not in ("completed", "rejected", "cancelled"):
            orders[oid]["status"] = "cancelled"
            found = oid
            break
    save_json(ORDER_FILE, orders)
    if found:
        await update.message.reply_text(f"✅ Your pending sell (Order {found}) has been cancelled.")
        await send_to_admins(context, f"ℹ️ User {uid} cancelled Order {found}.")
    else:
        await update.message.reply_text("ℹ️ You have no pending sell to cancel.")

# ================== WITHDRAW FLOW ==================
async def user_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    users = load_json(USER_FILE)
    withdraws = load_json(WITHDRAW_FILE)
    uid = str(query.from_user.id)

    if data == "continue_menu":
        if uid in users:
            users[uid]["joined"] = True
            save_json(USER_FILE, users)
        await query.edit_message_text(
            "🎉 Welcome to Robot!\n\n"
            "Enter your phone number with the country code.\n"
            "Example: +62xxxxxxx\n\n"
            "Type /cap to see available countries."
        )

    elif data == "withdraw":
        if uid not in users:
            await query.edit_message_text("❌ Please /start first.")
            return
        bal = users[uid]["balance"]
        if bal < 3:
            await query.edit_message_text("⚠️ Insufficient balance (minimum $3).")
        else:
            kb = [
                [InlineKeyboardButton("💳 Withdrawal Card", callback_data="withdraw_card")],
                [InlineKeyboardButton("💎 Withdrawal TRX", callback_data="withdraw_trx")]
            ]
            await query.edit_message_text("How you want to withdraw:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "withdraw_card":
        withdraws[uid] = {"method": "card", "step": "awaiting_address"}
        save_json(WITHDRAW_FILE, withdraws)
        await query.edit_message_text("✅ Send your card info")

    elif data == "withdraw_trx":
        withdraws[uid] = {"method": "trx", "step": "awaiting_address"}
        save_json(WITHDRAW_FILE, withdraws)
        await query.edit_message_text("✅ Send your TRX address")

    elif data == "withdraw_confirm_yes":
        if uid in withdraws and withdraws[uid].get("address"):
            users = load_json(USER_FILE)
            bal = users[uid]["balance"]
            amount = bal
            users[uid]["balance"] = 0.0
            save_json(USER_FILE, users)

            details = withdraws[uid]
            msg = (f"💸 New withdrawal request\n"
                   f"👤 User: {users[uid]['name']} ({uid})\n"
                   f"💰 Amount: ${amount:.2f}\n"
                   f"💳 Method: {details['method']}\n"
                   f"📍 Address: {details['address']}\n"
                   f"🕒 Time: {utc_now_str()}")
            await send_to_admins(context, msg)
            await query.edit_message_text("✅ Your withdrawal request has been sent to admin.")
            withdraws.pop(uid, None)
            save_json(WITHDRAW_FILE, withdraws)

    elif data == "withdraw_confirm_no":
        withdraws.pop(uid, None)
        save_json(WITHDRAW_FILE, withdraws)
        await query.edit_message_text("❌ Withdrawal cancelled.")

# ================== MESSAGE HANDLER ==================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    uid = str(update.effective_user.id)
    withdraws = load_json(WITHDRAW_FILE)

    # Withdrawal address flow
    if uid in withdraws and withdraws[uid].get("step") == "awaiting_address":
        withdraws[uid]["address"] = text
        withdraws[uid]["step"] = "confirming"
        save_json(WITHDRAW_FILE, withdraws)
        kb = [
            [InlineKeyboardButton("✅ Yes", callback_data="withdraw_confirm_yes"),
             InlineKeyboardButton("❌ No", callback_data="withdraw_confirm_no")]
        ]
        await update.message.reply_text(
            f"❗ Verify your address is correct, you cannot change it\n\n"
            f"❗ Are you sure about your {withdraws[uid]['method']} number/address and request?\n\n"
            f"📍 {text}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # Fallback for phone/otp goes here (same as before)...
    await update.message.reply_text("⚠️ Message not recognized.")

# ================== HEALTH SERVER ==================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

# ================== MAIN ==================
def main():
    start_health_server()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cap", cap))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("cancel", cancel_cmd))

    application.add_handler(CallbackQueryHandler(user_buttons, pattern=r"^(continue_menu|withdraw.*)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot running with POLLING + health server...")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
