# main.py
import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup

# -------- CONFIG ----------
TOKEN = os.getenv("BOT_TOKEN") or "8266639049:AAFvQYw-ax6y94S2zH_oMg7jA2Q1Dxh6yro"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 1378825382)
CHANNEL_LINK = "https://t.me/NR_receiver_News"
WEBHOOK_PATH = "/webhook"
# --------------------------

# Storage files
USER_FILE = "users.json"
ORDER_FILE = "orders.json"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure files exist
for f in (USER_FILE, ORDER_FILE):
    if not os.path.exists(f):
        with open(f, "w") as fh:
            json.dump({}, fh)

def load_json(fp):
    with open(fp, "r") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return {}

def save_json(fp, data):
    with open(fp, "w") as fh:
        json.dump(data, fh, indent=2)

users = load_json(USER_FILE)
orders = load_json(ORDER_FILE)

bot = Bot(token=TOKEN)
app = Flask(__name__)

# Price map for /cap logic
PRICE_MAP = {
    "+63": 0.65, "+503": 0.70, "+972": 0.80, "+970": 0.85, "+64": 1.10,
    "+90": 1.15, "+373": 1.15, "+299": 1.45, "+420": 1.65, "+886": 2.10,
    "+31": 2.15, "+34": 3.40, "+33": 3.50, "+49": 4.00
}

# Helpers
def now_utc_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def ensure_user(uid, fullname=""):
    if uid not in users:
        users[uid] = {
            "name": fullname or f"User {uid}",
            "balance": 0.0,
            "referrals": 0,
            "accounts_sold": 0
        }
        save_json(USER_FILE, users)

# ----- Command handlers (sync style) -----
def handle_start(chat_id, from_user):
    uid = str(from_user["id"])
    ensure_user(uid, from_user.get("full_name", ""))

    if users[uid].get("joined_channel") is not True:
        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("➡️ Continue to Menu", callback_data="continue_menu")]
        ]
        bot.send_message(chat_id=chat_id, text="👋 Welcome! Please join our channel first:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        bot.send_message(chat_id=chat_id,
                         text=("🎉 Welcome to Robot!\n\n"
                               "Enter your phone number with the country code.\n"
                               "Example: +62xxxxxxx\n\n"
                               "Type /cap to see available countries."))

def handle_cap(chat_id):
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
    bot.send_message(chat_id=chat_id, text=text)

def handle_balance(chat_id, user):
    uid = str(user["id"])
    if uid not in users:
        bot.send_message(chat_id=chat_id, text="⚠️ You don’t have a profile yet. Send /start first.")
        return
    u = users[uid]
    text = (f"👤 Name: {u['name']}\n"
            f"💰 Balance: ${u['balance']:.2f}\n"
            f"👥 Total Referrals: {u['referrals']}\n"
            f"📱 Accounts Sold: {u['accounts_sold']}\n"
            f"🕒 Last Check: {now_utc_str()}")
    kb = [[InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")]]
    bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(kb))

def handle_help(chat_id):
    bot.send_message(chat_id=chat_id, text="Use BotFather-set commands: /start /cap /balance /cancel /help")

def cancel_user_pending(chat_id, uid):
    uid = str(uid)
    if uid in orders and orders[uid].get("status") != "completed":
        orders.pop(uid, None)
        save_json(ORDER_FILE, orders)
        bot.send_message(chat_id=chat_id, text="✅ Your pending sell has been cancelled.")
    else:
        bot.send_message(chat_id=chat_id, text="ℹ️ You have no pending sell to cancel.")

# ----- Webhook processing route -----
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot)
    except Exception as e:
        logger.exception("Failed parsing update")
        return jsonify({"ok": False, "error": str(e)}), 400

    # Message
    if update.message:
        msg = update.message
        chat_id = msg.chat.id
        from_user = {"id": msg.from_user.id, "full_name": msg.from_user.full_name}

        text = (msg.text or "").strip()

        # Commands
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd == "/start":
                handle_start(chat_id, from_user)
            elif cmd == "/cap":
                handle_cap(chat_id)
            elif cmd == "/balance":
                handle_balance(chat_id, from_user)
            elif cmd == "/cancel":
                cancel_user_pending(chat_id, from_user["id"])
            elif cmd == "/help":
                handle_help(chat_id)
            else:
                bot.send_message(chat_id=chat_id, text="Command not handled.")
            return jsonify({"ok": True})

        # If user sends a phone number like +62...
        if text.startswith("+") and text[1:].isdigit():
            uid = str(from_user["id"])
            # Save user if missing
            ensure_user(uid, from_user.get("full_name", ""))

            # Prevent duplicates: if number already completed sold, reject
            for o in orders.values():
                if o.get("number") == text and o.get("status") == "completed":
                    bot.send_message(chat_id=chat_id, text="❌ This number has already been sold.")
                    return jsonify({"ok": True})

            # Save order
            orders[uid] = {
                "number": text,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }
            save_json(ORDER_FILE, orders)

            bot.send_message(chat_id=chat_id, text="⏳ Processing please wait...")

            # Notify admin with buttons
            kb = [
                [InlineKeyboardButton("✅ Request OTP", callback_data=f"reqotp_{uid}")],
                [InlineKeyboardButton("❌ Cancel Deal", callback_data=f"cancel_{uid}")]
            ]
            bot.send_message(chat_id=ADMIN_ID, text=f"📩 New number submitted:\n{text}\nUser ID: {uid}", reply_markup=InlineKeyboardMarkup(kb))
            return jsonify({"ok": True})

        # OTP submission (user sending code) — check if admin requested OTP
        uid = str(from_user["id"])
        if uid in orders and orders[uid].get("status") == "otp_requested":
            otp = text
            orders[uid]["otp"] = otp
            orders[uid]["status"] = "otp_submitted"
            orders[uid]["otp_submitted_at"] = datetime.utcnow().isoformat()
            save_json(ORDER_FILE, orders)

            # Send OTP to admin with approve/retry/reject
            kb = [
                [InlineKeyboardButton("🔄 Request Another Code", callback_data=f"admin_retry_{uid}")],
                [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{uid}")],
                [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{uid}")]
            ]
            bot.send_message(chat_id=ADMIN_ID, text=f"🔐 OTP received for User {uid}\nNumber: {orders[uid]['number']}\nOTP: {otp}", reply_markup=InlineKeyboardMarkup(kb))
            bot.send_message(chat_id=chat_id, text="✅ OTP received. Please wait for admin review.")
            return jsonify({"ok": True})

        # Unknown text
        bot.send_message(chat_id=chat_id, text="⚠️ Message not recognized. Send phone number (+countrycode) or use /cap.")
        return jsonify({"ok": True})

    # Callback query (inline button pressed)
    if update.callback_query:
        cq = update.callback_query
        data = cq.data or ""
        from_id = str(cq.from_user.id)

        # withdraw by user
        if data == "withdraw":
            uid = from_id
            if uid not in users:
                bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text="⚠️ You don’t have a profile yet. Send /start first.")
            else:
                bal = users[uid]["balance"]
                if bal < 3:
                    bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text="⚠️ Insufficient balance (minimum $3).")
                else:
                    bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text="✅ Withdrawal request submitted! Admin will process.")
                    bot.send_message(chat_id=ADMIN_ID, text=f"Withdrawal request from user {uid}. Amount: ${bal:.2f}")
            return jsonify({"ok": True})

        # Admin actions
        if data.startswith("reqotp_") or data.startswith("admin_reqotp_"):
            parts = data.split("_")
            order_uid = parts[1]
            if order_uid in orders:
                orders[order_uid]["status"] = "otp_requested"
                orders[order_uid]["otp_requested_at"] = datetime.utcnow().isoformat()
                save_json(ORDER_FILE, orders)
                # Tell user to enter OTP
                bot.send_message(chat_id=int(order_uid), text=f"🇹🇼 Enter the code sent to the number {orders[order_uid]['number']}")
                bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text=f"✅ OTP requested from user {order_uid}.")
            else:
                bot.answer_callback_query(callback_query_id=cq.id, text="Order not found.")
            return jsonify({"ok": True})

        if data.startswith("cancel_"):
            order_uid = data.split("_",1)[1]
            if order_uid in orders:
                orders[order_uid]["status"] = "cancelled"
                save_json(ORDER_FILE, orders)
                bot.send_message(chat_id=int(order_uid), text="❌ Your deal has been cancelled by admin.")
                bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text=f"❌ Order from {order_uid} cancelled.")
            else:
                bot.answer_callback_query(callback_query_id=cq.id, text="Order not found.")
            return jsonify({"ok": True})

        if data.startswith("admin_reject_"):
            order_uid = data.split("_",2)[2] if "_" in data else data.split("_",1)[1]
            if order_uid in orders:
                orders[order_uid]["status"] = "rejected"
                save_json(ORDER_FILE, orders)
                bot.send_message(chat_id=int(order_uid), text="❌ Your sell request has been rejected.")
                bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text=f"❌ Order {order_uid} rejected.")
            else:
                bot.answer_callback_query(callback_query_id=cq.id, text="Order not found.")
            return jsonify({"ok": True})

        if data.startswith("admin_retry_"):
            order_uid = data.split("_",2)[2] if "_" in data else data.split("_",1)[1]
            if order_uid in orders:
                orders[order_uid]["status"] = "otp_requested"
                save_json(ORDER_FILE, orders)
                bot.send_message(chat_id=int(order_uid), text=f"🔄 Please send another OTP for number {orders[order_uid]['number']}.")
                bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text=f"🔄 Requested another OTP from {order_uid}.")
            else:
                bot.answer_callback_query(callback_query_id=cq.id, text="Order not found.")
            return jsonify({"ok": True})

        if data.startswith("admin_approve_"):
            order_uid = data.split("_",2)[2] if "_" in data else data.split("_",1)[1]
            if order_uid in orders:
                num = orders[order_uid]["number"]
                price = 0.0
                for prefix, p in PRICE_MAP.items():
                    if num.startswith(prefix):
                        price = p
                        break
                # update user
                ensure_user(order_uid)
                users[order_uid]["balance"] += price
                users[order_uid]["accounts_sold"] = users[order_uid].get("accounts_sold",0) + 1
                save_json(USER_FILE, users)
                # finalize order
                orders[order_uid]["status"] = "completed"
                orders[order_uid]["price"] = price
                orders[order_uid]["completed_at"] = datetime.utcnow().isoformat()
                save_json(ORDER_FILE, orders)
                bot.send_message(chat_id=int(order_uid), text=(f"✅ Your account has been successfully sold!\n💰 ${price:.2f} credited to your balance."))
                bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text=f"✅ Order {order_uid} approved and user credited ${price:.2f}.")
            else:
                bot.answer_callback_query(callback_query_id=cq.id, text="Order not found.")
            return jsonify({"ok": True})

        # continue_menu action - mark joined channel then show menu
        if data == "continue_menu":
            uid = str(cq.from_user.id)
            ensure_user(uid, cq.from_user.full_name)
            users[uid]["joined_channel"] = True
            save_json(USER_FILE, users)
            bot.edit_message_text(chat_id=cq.message.chat.id, message_id=cq.message.message_id, text="Thanks for joining! Now send a phone number (+code) or type /cap.")
            return jsonify({"ok": True})

    return jsonify({"ok": True})


@app.route("/", methods=["GET"])
def root():
    return "Bot is running", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Note: webhook must be set to https://<your-render-app>.onrender.com/webhook
    app.run(host="0.0.0.0", port=port)
