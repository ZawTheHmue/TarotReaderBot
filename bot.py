import logging
import json
import random
import asyncio
import http.server
import threading
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config

# Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Tarot Data Load လုပ်ခြင်း
try:
    with open('tarot_data.json', 'r', encoding='utf-8') as f:
        TAROT_DATA = json.load(f)
except Exception as e:
    logger.error(f"Error loading tarot_data.json: {e}")
    TAROT_DATA = {}

# User များ၏ နေ့စဉ်ဗေဒင်မေးထားသော မှတ်တမ်း (Memory တွင် ခေတ္တသိမ်းသည်)
# Format: {user_id: "YYYY-MM-DD"}
USER_USAGE_LOG = {}

# Bot ထဲသို့ ဝင်ရောက်လာသော User IDs များကို Broadcast ရန်အတွက် သိမ်းဆည်းခြင်း
ALL_USERS = set()

# ကတ်ကျောဘက်မျက်နှာပြင်ပုံ (GIF သို့မဟုတ် 3D Flip သဏ္ဌာန်ပြရန် သင့်တော်ရာ URL)
CARD_BACK_IMAGE = "https://raw.githubusercontent.com/ColCard%20Tarot/CardBack/main/back.png" 

# HTML custom styling သုံး၍ အနီရောင် စာသားထွက်ပေါ်စေရန် သုံးသော စာလုံးပုံစံ
RED_TEXT_START = "<code>"
RED_TEXT_END = "</code>"

# Render ၏ Port Scan Timeout Error ကို ကျော်ဖြတ်ရန် Dummy Web Server တည်ဆောက်ခြင်း
def run_health_server():
    port = int(os.getenv("PORT", 10000))  # Render မှ သတ်မှတ်ပေးသော Port (Default: 10000)
    server_address = ('', port)
    
    # ရိုးရှင်းသော HTTP Request Handler (Render ရဲ့ Port Check ကို OK ပြန်ရန်)
    class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is alive and running!")

    httpd = http.server.HTTPServer(server_address, HealthCheckHandler)
    logger.info(f"Dummy Health Check Server Running on Port {port}...")
    httpd.serve_forever()

# Contact with Astrologer Button
def get_contact_button():
    url = f"https://t.me/{config.CREATOR_USERNAME}" if config.CREATOR_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact with Astrologer(10000MMK)", url=url)]
    ])

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)
    
    # Creator ဆိုလျှင် Admin Keyboard ပြမည်
    if user_id == config.CREATOR_ID:
        keyboard = [['📢 Send Notification (Broadcast)']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("မင်္ဂလာပါ Creator ဗျာ။ သင်သည် အကန့်အသတ်မရှိ အသုံးပြုနိုင်ပါသည်။", reply_markup=reply_markup)
    
    # Tarot စတင်ရန် Inline Button ပြခြင်း
    inline_keyboard = [[InlineKeyboardButton("🔮 Tarot ဗေဒင်ဟောကိန်းရယူမယ်", callback_data="start_tarot")]]
    await update.message.reply_text(
        "🔮 Tarot Reader Bot မှ ကြိုဆိုပါတယ်ဗျာ။ အောက်ပါခလုတ်ကိုနှိပ်၍ ဗေဒင်မေးမြန်းနိုင်ပါသည်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

# General User များ စာသားပေးပို့ခြင်းကို ပိတ်ပင်ခြင်း (Restriction)
async def restrict_text_messages(update: Update, context: Context
