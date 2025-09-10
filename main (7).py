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

# Storage files (local JSON)
USER_FILE = "users.json"
ORDER_FILE = "orders.json"

# ✅ Updated Prices by phone prefix
PRICE_MAP = {
    "+886": 2.10,  # Taiwan
    "+46": 1.60,   # Norway
    "+31": 2.10,   # Netherlands
    "+34": 3.10,   # Spain
    "+48": 1.40,   # Poland
    "+853": 1.55,  # Macau
    "+40": 1.55,   # Romania
    "+30": 1.70,   # Greece
    "+994": 1.20,  # Azerbaijan
    "+216": 0.60,  # Tunisia
    "+49": 3.10,   # Germany
    "+43": 1.60,   # Austria
    "+420": 1.65,  # Czech Republic
    "+353": 1.55,  # Ireland
    "+351": 1.80,  # Portugal
    "+505": 0.85,  # Nicaragua
    "+595": 1.00,  # Paraguay
    "+63": 0.63,   # Philippines
    "+970": 0.85,  # Palestine
    "+972": 0.80,  # Israel
    "+593": 0.90,  # Ecuador
    "+966": 1.95   # Saudi Arabia
}

# ✅ Updated CAP_TEXT
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

# ================== WITHDRAW LOGIC ==================
async def user_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    users = load_json(USER_FILE)
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
        return

    if data == "withdraw":
        if uid not in users:
            await query.edit_message_text("❌ Please /start first.")
            return
        bal = users[uid]["balance"]
        if bal < 3:
            await query.edit_message_text("⚠️ Insufficient balance (minimum $3).")
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Withdrawal Card", callback_data="withdraw_card")],
                [InlineKeyboardButton("💎 Withdrawal TRX", callback_data="withdraw_trx")]
            ])
            await query.edit_message_text("How you want to withdraw:", reply_markup=kb)
        return

    # Withdrawal card
    if data == "withdraw_card":
        context.user_data["withdraw_method"] = "Card"
        await query.edit_message_text("✅ Send your card info")
        return

    if data == "withdraw_trx":
        context.user_data["withdraw_method"] = "TRX"
        await query.edit_message_text("✅ Send your TRX address")
        return

    if data == "confirm_withdraw_yes":
        method = context.user_data.get("withdraw_method")
        address = context.user_data.get("withdraw_address")
        users = load_json(USER_FILE)
        bal = users[uid]["balance"]
        users[uid]["balance"] = 0.0
        save_json(USER_FILE, users)

        await query.edit_message_text("✅ Your withdrawal request has been sent to admin.")

        await send_to_admins(
            context,
            text=f"💸 Withdrawal Request\nUser: {uid}\nMethod: {method}\nAddress: {address}\nAmount: ${bal:.2f}\nTime: {utc_now_str()}"
        )
        return

    if data == "confirm_withdraw_no":
        await query.edit_message_text("❌ Withdrawal cancelled.")
        return

# ================== MESSAGE HANDLER ==================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    uid = str(update.effective_user.id)

    # Handle withdraw address entry
    if "withdraw_method" in context.user_data and "withdraw_address" not in context.user_data:
        context.user_data["withdraw_address"] = text
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes", callback_data="confirm_withdraw_yes"),
             InlineKeyboardButton("❌ No", callback_data="confirm_withdraw_no")]
        ])
        await update.message.reply_text(
            "❗️ Verify your address is correct, you cannot change it\n\n"
            f"❗️Are you sure about your {context.user_data['withdraw_method']} number/address and request?\n\n"
            f"{text}",
            reply_markup=kb
        )
        return

    # Existing logic (phone numbers & OTP) remains unchanged...
    # ... keep the rest of your message_handler code intact ...

# (keep admin_buttons, health server, and main() unchanged)
